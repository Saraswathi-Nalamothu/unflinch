"""
Unflinch – AI Interview Prep Assistant
FastAPI Backend – All fixes applied
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

app = FastAPI(title="Unflinch API", version="3.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALL_FILLERS = [
    "um", "uh", "umm", "uhh", "hmm", "hm",
    "like", "so", "actually", "basically", "literally",
    "you know", "you know what i mean", "i mean",
    "right", "okay", "ok", "well",
    "kinda", "kind of", "sort of", "sorta",
    "anyway", "anyways",
    "honestly", "truthfully", "frankly",
    "obviously", "definitely", "absolutely", "totally",
    "essentially", "generally", "typically",
]

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
    for filler in ALL_FILLERS:
        pattern = r"\b" + re.escape(filler) + r"\b"
        matches = re.findall(pattern, text_lower)
        count += len(matches)
    return count

def get_filler_breakdown(text: str) -> dict:
    text_lower = text.lower()
    breakdown = {}
    for filler in ALL_FILLERS:
        pattern = r"\b" + re.escape(filler) + r"\b"
        matches = re.findall(pattern, text_lower)
        if matches:
            breakdown[filler] = len(matches)
    return breakdown

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

def voice_tip(filler_count, pause_count, speech_rate, filler_breakdown=None):
    tips = []
    if filler_count >= 1:
        top_fillers = ""
        if filler_breakdown:
            top = sorted(filler_breakdown.items(), key=lambda x: -x[1])[:2]
            top_fillers = " (especially '" + "', '".join(f for f, _ in top) + "')"
        tips.append((filler_count + 2, f"You used {filler_count} filler word(s){top_fillers}. Practice pausing silently — it sounds more confident than fillers."))
    if pause_count >= 2:
        tips.append((pause_count, f"You had {pause_count} long pause(s). Use bridging phrases like 'That's a great question...' to keep momentum."))
    if speech_rate < 1.8:
        tips.append((5, f"You spoke slowly at {speech_rate:.1f} w/s. Aim for 2-3 words/second to sound more energetic."))
    if speech_rate > 3.5:
        tips.append((4, f"You spoke very fast at {speech_rate:.1f} w/s. Slow down — clarity beats speed in interviews."))
    if not tips:
        return f"Great delivery at {speech_rate:.1f} w/s! Your pace and clarity were spot on."
    tips.sort(key=lambda x: -x[0])
    return tips[0][1]

def ai_analyze_answer(question_text, transcript, filler_count, pause_count, speech_rate, filler_breakdown=None):
    no_answer_phrases = [
        "i don't know","i dont know","i have no idea","not sure","i'm not sure",
        "im not sure","i cannot answer","sorry i don't","sorry i dont","no idea",
        "i have no","i'm unsure","not really sure",
    ]
    transcript_lower = transcript.lower().strip()
    is_blank = any(p in transcript_lower for p in no_answer_phrases) or len(transcript.split()) < 8

    # Determine the primary voice issue to give varied feedback
    voice_issues = []
    if filler_count >= 1:
        if filler_breakdown:
            top = sorted(filler_breakdown.items(), key=lambda x: -x[1])[:2]
            filler_detail = ", ".join(f"'{f}' ({c}x)" for f, c in top)
            voice_issues.append(f"filler words: {filler_detail} — total {filler_count}")
        else:
            voice_issues.append(f"{filler_count} filler word(s)")
    if pause_count >= 2:
        voice_issues.append(f"{pause_count} long pauses/gaps in speech")
    if speech_rate < 1.8:
        voice_issues.append(f"slow speech pace at {speech_rate:.1f} words/second")
    elif speech_rate > 3.5:
        voice_issues.append(f"fast speech at {speech_rate:.1f} words/second")
    else:
        voice_issues.append(f"good speech pace at {speech_rate:.1f} words/second")

    # Confidence assessment
    confidence_note = ""
    if speech_rate >= 1.8 and speech_rate <= 3.5 and filler_count <= 2 and pause_count <= 1:
        confidence_note = "Your delivery showed good confidence."
    elif speech_rate < 1.5:
        confidence_note = "Speaking at a slightly faster pace would boost your confidence projection."
    elif filler_count > 5:
        confidence_note = "Reducing fillers will make you sound significantly more confident and prepared."

    voice_summary = "; ".join(voice_issues)

    if is_blank:
        prompt = f"""You are a professional interview coach speaking directly to a candidate.

They were asked: "{question_text}"
They said: "{transcript}"

They struggled to answer. Help them by:
1. Explaining what the interviewer is really looking for
2. Giving them a complete model answer to learn from
3. Encouraging them about their delivery

IMPORTANT: Always use "you/your". Never say "the candidate". Be encouraging and specific.

Respond with ONLY this JSON (no markdown, no backticks):
{{"content_feedback": "2 sentences: explain what this question is testing and what a strong answer includes. Start with 'This question tests...'", "better_answer": "A complete confident model answer in first person (4-5 sentences). Use STAR: specific situation + action + measurable result. Make it impressive and realistic.", "voice_feedback": "One encouraging tip about your voice or confidence for next time.", "overall_tip": "The single most important thing you should do to prepare this answer before your real interview."}}"""
    else:
        prompt = f"""You are a professional interview coach giving detailed feedback directly to a candidate.

Question: "{question_text}"
Their answer: "{transcript}"
Voice analysis: {voice_summary}
{confidence_note}

Give thorough, specific feedback. IMPORTANT: Always say "you/your". Never say "the candidate". Be honest but encouraging.

Respond with ONLY this JSON (no markdown, no backticks):
{{"content_feedback": "2-3 sentences: first acknowledge what was genuinely strong in your answer, then precisely identify the missing element (specific example, quantifiable result, clearer structure, or deeper insight) that would make it excellent.", "better_answer": "Rewrite your answer in first person (4-5 sentences). Keep your ideas but improve with: clear STAR structure, specific numbers or outcomes, confident language, and a strong closing. Show exactly how to say it better.", "voice_feedback": "Specific feedback on: {voice_summary}. Give one concrete technique to improve it — not generic advice.", "overall_tip": "One direct, specific sentence: the single change that will most improve your next answer."}}"""

    raw = ""
    for attempt in range(3):
        try:
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert interview coach. ALWAYS use 'you'/'your' when addressing the candidate. NEVER say 'the candidate'. Give specific, actionable feedback. Respond with valid JSON only — no markdown, no backticks, no text outside the JSON object."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=750,
            )
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```json|```", "", raw).strip()
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
                    "voice_feedback":   vf or voice_tip(filler_count, pause_count, speech_rate, filler_breakdown),
                    "overall_tip":      ot or voice_tip(filler_count, pause_count, speech_rate, filler_breakdown),
                }
        except Exception as e:
            logger.error(f"AI analysis attempt {attempt+1} failed: {e} | raw: {raw[:200]}")
            continue

    # Meaningful fallback
    vt = voice_tip(filler_count, pause_count, speech_rate, filler_breakdown)
    if is_blank:
        return {
            "content_feedback": "This question tests your real-world experience and problem-solving approach. Prepare a specific story using the STAR method (Situation, Task, Action, Result).",
            "better_answer": "Structure your answer: 'In my experience, I faced [specific challenge]. I was responsible for [what needed to be done]. I approached it by [specific steps]. As a result, [measurable positive outcome].' Practice this out loud.",
            "voice_feedback": vt,
            "overall_tip": "Write a 2-minute story from your experience that answers this question and practice it 5 times out loud.",
        }
    else:
        return {
            "content_feedback": "Your answer addressed the question well. To make it stronger, add one specific example with a measurable result that proves your point.",
            "better_answer": "Try this structure: '[Acknowledge the situation] → [Specific action you took] → [Measurable result, e.g. improved by X%, completed in Y days] → [What you learned]'. This makes your answer concrete and memorable.",
            "voice_feedback": vt,
            "overall_tip": "End every answer with a specific result or outcome — it's what interviewers remember most.",
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
    experience_ctx = ("First-time candidate — include introductory questions about background and motivation."
                      if req.first_time else "Experienced candidate — ask deeper, role-specific questions.")
    round_guidance = {
        "First Round": "Background, motivation, cultural fit, basic role understanding.",
        "Technical":   "Deep technical skills, problem-solving, system design, coding concepts.",
        "HR":          "Salary expectations, work style, team dynamics, career goals.",
        "Final Round": "Leadership, strategic thinking, vision, company-specific scenarios.",
        "Case Study":  "Analytical thinking, structured problem-solving, data-driven decisions.",
    }.get(req.round, "Mix of behavioral and technical questions.")

    prompt = f"""{persona_style}

Interviewing at {req.company} for {req.role} ({req.round} — {round_guidance}).
{experience_ctx}

Generate exactly 5 highly specific interview questions:
1. Reference {req.company}'s actual products, industry, or known challenges
2. Directly relevant to {req.role} day-to-day responsibilities
3. Match real {req.round} difficulty at {req.company}
4. Mix behavioral (STAR), situational, technical questions
5. Realistic questions a real interviewer would ask

JSON array only: ["Q1?","Q2?","Q3?","Q4?","Q5?"]"""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL_QUALITY,
            messages=[
                {"role":"system","content":"Expert interviewer. Valid JSON array only. No markdown."},
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
            f"How do you stay updated with developments relevant to {req.company}'s work?",
            "Describe a challenging project you led. What was your approach and outcome?",
            f"Why {req.company} specifically, and how does this {req.role} role fit your goals?",
            "Tell me about a time you had to learn something quickly under pressure.",
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

        filler_count     = count_fillers(transcript)
        filler_breakdown = get_filler_breakdown(transcript)
        pause_count      = count_long_pauses(tmp_path)
        speech_rate      = round(word_count / max(duration, 1.0), 2)
        nervousness      = compute_nervousness(filler_count, pause_count, speech_rate, recovery_time)
        ai_feedback      = ai_analyze_answer(
            question_text or "Interview question",
            transcript, filler_count, pause_count, speech_rate, filler_breakdown
        )
        tip = ai_feedback["overall_tip"] or voice_tip(filler_count, pause_count, speech_rate, filler_breakdown)

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

        # Determine strengths
        strengths = []
        if avg_fillers < 2: strengths.append("low filler word usage")
        if avg_pauses < 1:  strengths.append("smooth speech flow with minimal pauses")
        if 1.8 <= avg_rate <= 3.2: strengths.append(f"excellent speech pace at {avg_rate:.1f} w/s")
        if avg_score < 35:  strengths.append("calm and confident overall delivery")
        strength_text = " and ".join(strengths) if strengths else "your willingness to practice and improve"

        prompt = f"""You are a professional interview coach writing directly to a candidate. Always use "you/your".

Their session data:
- Avg filler words per answer: {avg_fillers:.1f}
- Avg long pauses per answer: {avg_pauses:.1f}
- Avg speech rate: {avg_rate:.1f} words/second (ideal: 2.0-3.0)
- Nervousness score: {avg_score:.1f}/100 (lower is better)
- Strengths identified: {strength_text}

Write a structured improvement plan with these 4 parts:
1. **What You Did Well**: Acknowledge their genuine strength ({strength_text}) — make them feel confident.
2. **Your Key Weakness**: The single most impactful area to improve based on the data.
3. **Your Daily Drill**: One specific, actionable 5-minute daily exercise to fix the weakness.
4. **Your Next Target**: One measurable goal for the next practice session.

Be encouraging, specific, and talk directly to them. Under 200 words."""

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role":"user","content":prompt}],
            temperature=0.5, max_tokens=400,
        )
        return {"plan":response.choices[0].message.content.strip()}
    except Exception as e:
        logger.error(f"improvement plan error: {e}")
        return {"plan":"You showed great effort in this session! Focus on reducing filler words by practising silent pauses, maintain your 2-3 w/s speech rate, and always include a specific example with measurable results in your answers."}