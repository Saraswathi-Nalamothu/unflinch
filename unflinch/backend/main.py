"""
Unflinch – AI Interview Prep Assistant
FastAPI Backend – Uses Groq Whisper API (no local model = no memory issues)
"""

import os
import re
import json
import tempfile
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import librosa
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq
from supabase import create_client, Client

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPABASE_URL              = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
GROQ_API_KEY              = os.getenv("GROQ_API_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
groq_client      = Groq(api_key=GROQ_API_KEY)

app = FastAPI(title="Unflinch API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FILLER_WORDS = ["um","uh","like","so","actually","basically","you know","right","well","kinda","kind of"]
IDEAL_SPEECH_RATE = 2.5
GROQ_MODEL = "llama-3.1-8b-instant"
GROQ_MODEL_QUALITY = "llama-3.3-70b-versatile"

PERSONA_STYLES = {
    "friendly": "You are a warm, supportive HR interviewer. Focus on culture fit, values, soft skills.",
    "strict":   "You are a strict technical interviewer. Ask deep technical, system design questions. Be direct.",
    "startup":  "You are an energetic startup founder. Ask unconventional, vision-focused questions.",
    "pressure": "You are a stress interviewer. Ask tough questions and test resilience under pressure.",
}

def verify_jwt(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]
    try:
        user = supabase.auth.get_user(token)
        return user.user.id
    except Exception as e:
        logger.error(f"JWT verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

class GenerateQuestionsRequest(BaseModel):
    session_id: str
    company: str
    role: str
    round: str
    first_time: bool
    persona: str = "friendly"

class SaveSessionRequest(BaseModel):
    session_id: str

class CreateSessionRequest(BaseModel):
    company: str
    role: str
    round: str
    first_time: bool
    distraction_enabled: bool

def count_fillers(text: str) -> int:
    text_lower = text.lower()
    count = 0
    for filler in FILLER_WORDS:
        pattern = r"\b" + re.escape(filler) + r"\b"
        count += len(re.findall(pattern, text_lower))
    return count

def count_long_pauses(audio_path: str, min_silence_duration: float = 1.5,
                      silence_threshold_db: float = -40.0) -> int:
    try:
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        db = librosa.amplitude_to_db(rms, ref=np.max)
        frame_duration = 512 / sr
        is_silence = db < silence_threshold_db
        pauses, silence_start = 0, None
        for i, silent in enumerate(is_silence):
            if silent and silence_start is None:
                silence_start = i
            elif not silent and silence_start is not None:
                if (i - silence_start) * frame_duration >= min_silence_duration:
                    pauses += 1
                silence_start = None
        if silence_start is not None:
            if (len(is_silence) - silence_start) * frame_duration >= min_silence_duration:
                pauses += 1
        return pauses
    except Exception as e:
        logger.error(f"Pause detection error: {e}")
        return 0

def compute_nervousness(filler_count, pause_count, speech_rate, recovery_time=None):
    filler_norm  = min(filler_count / 10.0, 1.0)
    pause_norm   = min(pause_count  /  5.0, 1.0)
    rate_penalty = max(0.0, (IDEAL_SPEECH_RATE - speech_rate) / IDEAL_SPEECH_RATE)
    score = (filler_norm * 0.4 + pause_norm * 0.4 + rate_penalty * 0.2) * 100
    if recovery_time:
        score = min(100, score + min(recovery_time / 10.0, 1.0) * 15)
    return round(score, 1)

def voice_tip(filler_count, pause_count, speech_rate):
    tips = []
    if filler_count >= 3: tips.append((filler_count, f"You used {filler_count} filler word(s). Pause silently instead of saying 'um' or 'uh'."))
    if pause_count >= 2:  tips.append((pause_count, f"You had {pause_count} long pause(s). Use bridging phrases to stay fluid."))
    if speech_rate < 1.5: tips.append((5, f"You spoke slowly ({speech_rate:.1f} w/s). Aim for 2-3 words/second."))
    if speech_rate > 3.5: tips.append((4, f"You spoke very fast ({speech_rate:.1f} w/s). Slow down for clarity."))
    if not tips: return "Great delivery! Keep that pace and clarity."
    tips.sort(key=lambda x: -x[0])
    return tips[0][1]

def ai_analyze_answer(question_text, transcript, filler_count, pause_count, speech_rate):
    no_answer_phrases = [
        "i don't know","i dont know","i have no idea","not sure","i'm not sure",
        "im not sure","i cannot answer","sorry i don't","sorry i dont","no idea",
    ]
    transcript_lower = transcript.lower().strip()
    is_blank = any(p in transcript_lower for p in no_answer_phrases) or len(transcript.split()) < 8

    if is_blank:
        prompt = f"""Interview question: "{question_text}"
Candidate said: "{transcript}"
They didn't know the answer. Teach them briefly.

JSON only (no markdown):
{{"content_feedback":"Why this question matters (1 sentence).","better_answer":"Model answer in first person (3-4 sentences).","voice_feedback":"One delivery tip.","overall_tip":"One action to prepare this answer."}}"""
    else:
        prompt = f"""Question: "{question_text}"
Answer: "{transcript}"
Metrics: {filler_count} fillers, {pause_count} pauses, {speech_rate:.1f}w/s rate.

JSON only (no markdown):
{{"content_feedback":"What was good and what was missing (2 sentences).","better_answer":"Improved version in first person (3-4 sentences).","voice_feedback":"One delivery tip based on metrics.","overall_tip":"Single most important improvement."}}"""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role":"system","content":"Interview coach. JSON only, no markdown."},
                {"role":"user","content":prompt}
            ],
            temperature=0.4,
            max_tokens=400,
        )
        raw = re.sub(r"```json|```","",response.choices[0].message.content.strip()).strip()
        result = json.loads(raw)
        return {
            "content_feedback": result.get("content_feedback",""),
            "better_answer":    result.get("better_answer",""),
            "voice_feedback":   result.get("voice_feedback",""),
            "overall_tip":      result.get("overall_tip",""),
        }
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        return {
            "content_feedback": "Analysis unavailable.",
            "better_answer":    "",
            "voice_feedback":   voice_tip(filler_count, pause_count, speech_rate),
            "overall_tip":      voice_tip(filler_count, pause_count, speech_rate),
        }

@app.get("/health")
def health():
    return {"status": "ok", "cors": "enabled"}

@app.post("/create_session")
def create_session(req: CreateSessionRequest, user_id: str = Depends(verify_jwt)):
    try:
        result = supabase.table("sessions").insert({
            "user_id":user_id,"company":req.company,"role":req.role,
            "round":req.round,"first_time":req.first_time,
            "distraction_enabled":req.distraction_enabled,"status":"in_progress",
        }).execute()
        return {"session_id":result.data[0]["id"],"session":result.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_questions")
def generate_questions(req: GenerateQuestionsRequest, user_id: str = Depends(verify_jwt)):
    persona_style = PERSONA_STYLES.get(req.persona, PERSONA_STYLES["friendly"])
    experience_ctx = ("First-time candidate — include introductory questions."
                      if req.first_time else "Experienced candidate — ask deeper questions.")
    round_guidance = {
        "First Round": "Background, motivation, cultural fit.",
        "Technical":   "Technical skills, problem-solving, system design.",
        "HR":          "Salary, work style, team dynamics, career goals.",
        "Final Round": "Leadership, strategic thinking, company scenarios.",
        "Case Study":  "Analytical thinking, structured problem-solving.",
    }.get(req.round, "Mix behavioral and technical questions.")

    prompt = f"""{persona_style}
Interviewing at {req.company} for {req.role} ({req.round}: {round_guidance}).
{experience_ctx}

Generate 5 interview questions specific to {req.company} and {req.role}.
JSON array only: ["Q1?","Q2?","Q3?","Q4?","Q5?"]"""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL_QUALITY,
            messages=[
                {"role":"system","content":"Expert interviewer. Valid JSON array only."},
                {"role":"user","content":prompt}
            ],
            temperature=0.7, max_tokens=800,
        )
        raw = re.sub(r"```json|```","",response.choices[0].message.content.strip()).strip()
        questions_list = json.loads(raw)
        if not isinstance(questions_list,list) or len(questions_list)<5:
            raise ValueError("Invalid format")
        rows = [{"session_id":req.session_id,"question_text":q,"order_index":i}
                for i,q in enumerate(questions_list[:5])]
        result = supabase.table("questions").insert(rows).execute()
        return {"questions":result.data}
    except Exception as e:
        logger.error(f"generate_questions error: {e}")
        fallback = [
            f"Tell me about your experience relevant to {req.role} at {req.company}.",
            "Describe a challenging project and how you overcame it.",
            "Where do you see yourself in 5 years?",
            f"What excites you about working at {req.company}?",
            "Tell me about a time you worked under pressure.",
        ]
        rows = [{"session_id":req.session_id,"question_text":q,"order_index":i}
                for i,q in enumerate(fallback)]
        result = supabase.table("questions").insert(rows).execute()
        return {"questions":result.data}

@app.post("/analyze_answer")
async def analyze_answer(
    session_id:    str             = Form(...),
    question_id:   str             = Form(...),
    question_text: str             = Form(""),
    recovery_time: Optional[float] = Form(None),
    audio:         UploadFile      = File(...),
    user_id:       str             = Depends(verify_jwt),
):
    suffix = Path(audio.filename).suffix if audio.filename else ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
        # Step 1: Transcribe using Groq Whisper API (no local model needed!)
        with open(tmp_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(Path(tmp_path).name, audio_file),
                model="whisper-large-v3-turbo",
                response_format="verbose_json",
            )
        transcript = transcription.text.strip() if transcription.text else ""
        duration = getattr(transcription, 'duration', None) or 30.0

        # Step 2: Check for no speech
        word_count = len(transcript.split())
        if word_count < 3:
            return {
                "answer_id":None,"transcript":transcript,"filler_count":0,"pause_count":0,
                "speech_rate":0.0,"nervousness_score":0,"improvement_tip":"",
                "duration":round(duration,1),"content_feedback":"","better_answer":"","voice_feedback":"","no_speech":True,
            }

        # Step 3: Voice metrics
        filler_count = count_fillers(transcript)
        pause_count  = count_long_pauses(tmp_path)
        speech_rate  = round(word_count / max(duration, 1.0), 2)
        nervousness  = compute_nervousness(filler_count, pause_count, speech_rate, recovery_time)

        # Step 4: AI feedback
        ai_feedback = ai_analyze_answer(question_text or "Interview question", transcript, filler_count, pause_count, speech_rate)
        tip = ai_feedback["overall_tip"] or voice_tip(filler_count, pause_count, speech_rate)

        # Step 5: Store
        result = supabase.table("answers").insert({
            "session_id":session_id,"question_id":question_id,
            "transcript":transcript,"filler_count":filler_count,
            "pause_count":pause_count,"speech_rate":speech_rate,
            "nervousness_score":nervousness,"improvement_tip":tip,
            "recovery_time":recovery_time,
        }).execute()

        return {
            "answer_id":result.data[0]["id"],"transcript":transcript,
            "filler_count":filler_count,"pause_count":pause_count,
            "speech_rate":speech_rate,"nervousness_score":nervousness,
            "improvement_tip":tip,"duration":round(duration,1),
            "content_feedback":ai_feedback["content_feedback"],
            "better_answer":ai_feedback["better_answer"],
            "voice_feedback":ai_feedback["voice_feedback"],
            "no_speech":False,
        }
    finally:
        os.unlink(tmp_path)

@app.get("/get_session/{session_id}")
def get_session(session_id: str, user_id: str = Depends(verify_jwt)):
    try:
        session   = supabase.table("sessions").select("*").eq("id",session_id).single().execute()
        questions = supabase.table("questions").select("*").eq("session_id",session_id).order("order_index").execute()
        answers   = supabase.table("answers").select("*").eq("session_id",session_id).execute()
        return {"session":session.data,"questions":questions.data,"answers":answers.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard")
def dashboard(user_id: str = Depends(verify_jwt)):
    try:
        sessions = supabase.table("sessions").select("*").eq("user_id",user_id).order("created_at",desc=True).execute()
        return {"sessions":sessions.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/save_session")
def save_session(req: SaveSessionRequest, user_id: str = Depends(verify_jwt)):
    try:
        answers = supabase.table("answers").select("nervousness_score").eq("session_id",req.session_id).execute()
        scores  = [a["nervousness_score"] for a in answers.data if a["nervousness_score"] is not None]
        overall = round(sum(scores)/len(scores),1) if scores else 0.0
        supabase.table("sessions").update({"status":"completed","overall_nervousness":overall}).eq("id",req.session_id).execute()
        return {"status":"completed","overall_nervousness":overall}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_improvement_plan")
def generate_improvement_plan(req: dict, user_id: str = Depends(verify_jwt)):
    session_id = req.get("session_id")
    try:
        answers = supabase.table("answers").select(
            "filler_count,pause_count,speech_rate,nervousness_score,improvement_tip"
        ).eq("session_id",session_id).execute()
        data = answers.data
        if not data: return {"plan":"No answers found for this session."}
        avg_fillers = sum(a["filler_count"] or 0 for a in data)/len(data)
        avg_pauses  = sum(a["pause_count"]  or 0 for a in data)/len(data)
        avg_rate    = sum(a["speech_rate"]   or 0 for a in data)/len(data)
        avg_score   = sum(a["nervousness_score"] or 0 for a in data)/len(data)

        prompt = f"""Interview coach. Write a short improvement plan.
Metrics: fillers={avg_fillers:.1f}/ans, pauses={avg_pauses:.1f}/ans, rate={avg_rate:.1f}w/s, nervousness={avg_score:.1f}/100.

3-part plan:
1. **Key Weakness**: Most impactful area.
2. **Daily Drill**: 5-minute exercise.
3. **Next Target**: One measurable goal.
Under 150 words. Encouraging tone."""

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role":"user","content":prompt}],
            temperature=0.6, max_tokens=300,
        )
        return {"plan":response.choices[0].message.content.strip()}
    except Exception as e:
        logger.error(f"improvement plan error: {e}")
        return {"plan":"Focus on reducing filler words, controlling your pace, and practising smooth transitions."}