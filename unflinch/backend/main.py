"""
Unflinch – AI Interview Prep Assistant
FastAPI Backend – Groq Whisper + robust AI analysis
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
    if filler_count >= 1:
        tips.append((filler_count + 2, f"You used {filler_count} filler word(s) like 'um' or 'uh'. Practice pausing silently instead — a brief pause sounds more confident than a filler."))
    if pause_count >= 2:
        tips.append((pause_count, f"You had {pause_count} long pause(s). Prepare bridging phrases like 'That's a great question, let me think...' to keep momentum."))
    if speech_rate < 1.8:
        tips.append((5, f"You spoke slowly at {speech_rate:.1f} w/s. Aim for 2-3 words/second — it sounds more energetic and confident."))
    if speech_rate > 3.5:
        tips.append((4, f"You spoke very fast at {speech_rate:.1f} w/s. Slow down — clarity always beats speed in interviews."))
    if not tips:
        return f"Good delivery at {speech_rate:.1f} words/second! Keep that natural pace and clarity."
    tips.sort(key=lambda x: -x[0])
    return tips[0][1]

def ai_analyze_answer(question_text, transcript, filler_count, pause_count, speech_rate):
    no_answer_phrases = [
        "i don't know","i dont know","i have no idea","not sure","i'm not sure",
        "im not sure","i cannot answer","sorry i don't","sorry i dont","no idea",
        "i have no","i'm unsure","not really sure",
    ]
    transcript_lower = transcript.lower().strip()
    is_blank = any(p in transcript_lower for p in no_answer_phrases) or len(transcript.split()) < 8

    # Build voice context
    voice_issues = []
    if filler_count >= 1: voice_issues.append(f"{filler_count} filler word(s)")
    if pause_count >= 2: voice_issues.append(f"{pause_count} long pause(s)")
    if speech_rate < 1.8: voice_issues.append("slow speech pace")
    if speech_rate > 3.5: voice_issues.append("fast speech pace")
    voice_summary = ", ".join(voice_issues) if voice_issues else "good delivery overall"

    if is_blank:
        prompt = f"""You are a professional interview coach. The candidate could not answer this interview question.

Question: "{question_text}"
Candidate said: "{transcript}"

Respond with ONLY this JSON (no markdown, no extra text):
{{"content_feedback": "Explain in 1-2 sentences why interviewers ask this question and what they are really looking for.", "better_answer": "Write a complete, confident model answer in first person (4-5 sentences). Use STAR format: describe a specific situation, what action you took, and the positive result. Make it realistic and impressive.", "voice_feedback": "One encouraging tip about voice delivery for next attempt.", "overall_tip": "The single most important thing they should do to prepare this answer."}}"""
    else:
        prompt = f"""You are a professional interview coach reviewing this interview answer.

Question: "{question_text}"
Answer transcript: "{transcript}"
Voice metrics: {voice_summary}, speech rate {speech_rate:.1f} words/second

Analyze the CONTENT and DELIVERY thoroughly.

Respond with ONLY this JSON (no markdown, no extra text):
{{"content_feedback": "2-3 sentences: start with what was genuinely good, then identify the most important missing element (specific example, measurable result, or better structure).", "better_answer": "Rewrite their answer in first person (4-5 sentences), keeping their ideas but improving structure with STAR format, adding specifics, and making it more impactful. This should be clearly better than what they said.", "voice_feedback": "Specific actionable tip based on: {voice_summary}.", "overall_tip": "One sentence: the single most impactful change they can make to their next answer."}}"""

    raw = ""
    for attempt in range(3):
        try:
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert interview coach. Respond with valid JSON only. No markdown backticks. No text before or after the JSON object."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=700,
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```json|```", "", raw).strip()
            # Extract JSON object even if there's surrounding text
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                raw = match.group()
            parsed = json.loads(raw)
            cf = str(parsed.get("content_feedback", "")).strip()
            ba = str(parsed.get("better_answer", "")).strip()
            vf = str(parsed.get("voice_feedback", "")).strip()
            ot = str(parsed.get("overall_tip", "")).strip()
            if cf and ba:
                return {
                    "content_feedback": cf,
                    "better_answer":    ba,
                    "voice_feedback":   vf or voice_tip(filler_count, pause_count, speech_rate),
                    "overall_tip":      ot or voice_tip(filler_count, pause_count, speech_rate),
                }
        except Exception as e:
            logger.error(f"AI analysis attempt {attempt+1} failed: {e} | raw: {raw[:200]}")
            continue

    # Meaningful fallback — never "unavailable"
    vt = voice_tip(filler_count, pause_count, speech_rate)
    if is_blank:
        return {
            "content_feedback": f"This question tests your ability to handle real challenges relevant to the role. Interviewers want to see how you think and what you've actually done.",
            "better_answer": "Use the STAR method to answer: describe a Situation you faced, your Task or goal, the Actions you took step by step, and the Result you achieved. Prepare 2-3 real stories from your experience that you can adapt to this type of question.",
            "voice_feedback": vt,
            "overall_tip": "Write down a specific 2-minute story from your experience that answers this question, and practice it out loud 5 times.",
        }
    else:
        return {
            "content_feedback": "Your answer showed understanding of the topic. To make it stronger, add a specific real example with a measurable outcome using the STAR format (Situation, Task, Action, Result).",
            "better_answer": "Structure your answer like this: 'In my previous experience, I faced [specific situation]. I was responsible for [task]. I approached it by [specific actions]. As a result, [measurable positive outcome].' This makes your answer concrete and memorable.",
            "voice_feedback": vt,
            "overall_tip": "Always end your answer with a specific result or learning — it makes a lasting impression on the interviewer.",
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
    experience_ctx = ("This is a first-time candidate — include introductory questions about background and motivation."
                      if req.first_time else "Experienced candidate — ask deeper, role-specific questions.")
    round_guidance = {
        "First Round": "Background, motivation, cultural fit, basic role understanding.",
        "Technical":   "Deep technical skills, problem-solving, system design, coding concepts.",
        "HR":          "Salary expectations, work style, team dynamics, career goals.",
        "Final Round": "Leadership, strategic thinking, vision, company-specific scenarios.",
        "Case Study":  "Analytical thinking, structured problem-solving, data-driven decisions.",
    }.get(req.round, "Mix of behavioral and technical questions.")

    prompt = f"""{persona_style}

You are interviewing a candidate at {req.company} for the position of {req.role}.
Round: {req.round} — Focus: {round_guidance}
Candidate level: {experience_ctx}

Generate exactly 5 highly specific interview questions that:
1. Reference {req.company}'s actual products, industry, values, or known challenges
2. Are directly relevant to the day-to-day responsibilities of a {req.role}
3. Match the difficulty and style of a real {req.round} at {req.company}
4. Mix behavioral (STAR format), situational, and role-specific technical questions
5. Are realistic questions a real interviewer would actually ask

Respond with ONLY a JSON array of 5 strings. No explanation, no markdown.
["Question 1?", "Question 2?", "Question 3?", "Question 4?", "Question 5?"]"""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL_QUALITY,
            messages=[
                {"role":"system","content":"Expert interviewer. Respond with valid JSON array only. No markdown."},
                {"role":"user","content":prompt}
            ],
            temperature=0.7, max_tokens=900,
        )
        raw = re.sub(r"```json|```","",response.choices[0].message.content.strip()).strip()
        match = re.search(r'\[[\s\S]*\]', raw)
        if match:
            raw = match.group()
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
            f"Tell me about your most relevant experience for the {req.role} role at {req.company}.",
            f"How do you stay updated with the latest developments in your field relevant to {req.company}'s work?",
            "Describe a challenging project you led. What was your approach and what were the results?",
            f"Why do you want to work at {req.company} specifically, and how does this {req.role} role align with your goals?",
            "Tell me about a time you had to learn something quickly under pressure. How did you handle it?",
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
        # Transcribe using Groq Whisper API
        with open(tmp_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(Path(tmp_path).name, audio_file),
                model="whisper-large-v3-turbo",
                response_format="verbose_json",
            )
        transcript = transcription.text.strip() if transcription.text else ""
        duration = getattr(transcription, 'duration', None) or 30.0

        word_count = len(transcript.split())
        if word_count < 3:
            return {
                "answer_id":None,"transcript":transcript,"filler_count":0,"pause_count":0,
                "speech_rate":0.0,"nervousness_score":0,"improvement_tip":"",
                "duration":round(duration,1),"content_feedback":"","better_answer":"","voice_feedback":"","no_speech":True,
            }

        filler_count = count_fillers(transcript)
        pause_count  = count_long_pauses(tmp_path)
        speech_rate  = round(word_count / max(duration, 1.0), 2)
        nervousness  = compute_nervousness(filler_count, pause_count, speech_rate, recovery_time)
        ai_feedback  = ai_analyze_answer(question_text or "Interview question", transcript, filler_count, pause_count, speech_rate)
        tip = ai_feedback["overall_tip"] or voice_tip(filler_count, pause_count, speech_rate)

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

        prompt = f"""You are a professional interview coach. Write a personalised improvement plan based on this performance data.

Average filler words per answer: {avg_fillers:.1f}
Average long pauses per answer: {avg_pauses:.1f}
Average speech rate: {avg_rate:.1f} words/second (ideal: 2.0-3.0)
Overall nervousness score: {avg_score:.1f}/100 (lower is better)

Write a 3-part improvement plan:
1. **Key Weakness**: The single most impactful area to fix based on the data above.
2. **Daily Drill**: One specific, actionable 5-minute daily exercise to address it.
3. **Next Session Target**: One measurable goal for the next practice session.

Be specific, encouraging, and practical. Under 180 words."""

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role":"user","content":prompt}],
            temperature=0.5, max_tokens=350,
        )
        return {"plan":response.choices[0].message.content.strip()}
    except Exception as e:
        logger.error(f"improvement plan error: {e}")
        return {"plan":"Focus on reducing filler words by practising silent pauses, aim for 2-3 words/second speech rate, and always include a specific example with measurable results in your answers."}