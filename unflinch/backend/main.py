"""
Unflinch – AI Interview Prep Assistant
FastAPI Backend
"""

import os
import re
import uuid
import math
import json
import tempfile
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import librosa
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq
from supabase import create_client, Client
from faster_whisper import WhisperModel

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Initialise external clients
# ---------------------------------------------------------------------------

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# Load Whisper model once at startup (tiny = fast, base = better accuracy)
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
logger.info(f"Loading Whisper model: {WHISPER_MODEL_SIZE}")
whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
logger.info("Whisper model loaded.")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Unflinch API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

FILLER_WORDS = [
    "um", "uh", "like", "so", "actually", "basically",
    "you know", "right", "well", "kinda", "kind of",
]

IDEAL_SPEECH_RATE = 2.5  # words per second


def verify_jwt(authorization: str = Header(None)) -> str:
    """Verify Supabase JWT and return the user_id."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]
    try:
        user = supabase.auth.get_user(token)
        return user.user.id
    except Exception as e:
        logger.error(f"JWT verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class GenerateQuestionsRequest(BaseModel):
    session_id: str
    company: str
    role: str
    round: str
    first_time: bool


class SaveSessionRequest(BaseModel):
    session_id: str


class CreateSessionRequest(BaseModel):
    company: str
    role: str
    round: str
    first_time: bool
    distraction_enabled: bool


# ---------------------------------------------------------------------------
# Helper: filler word count
# ---------------------------------------------------------------------------

def count_fillers(text: str) -> int:
    text_lower = text.lower()
    count = 0
    for filler in FILLER_WORDS:
        # whole-word match
        pattern = r"\b" + re.escape(filler) + r"\b"
        count += len(re.findall(pattern, text_lower))
    return count


# ---------------------------------------------------------------------------
# Helper: pause detection with librosa
# ---------------------------------------------------------------------------

def count_long_pauses(audio_path: str, min_silence_duration: float = 1.5,
                      silence_threshold_db: float = -40.0) -> int:
    """Count silences longer than min_silence_duration seconds."""
    try:
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        # Convert to dB
        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        db = librosa.amplitude_to_db(rms, ref=np.max)
        hop_length = 512
        frame_duration = hop_length / sr

        is_silence = db < silence_threshold_db
        pauses = 0
        silence_start = None

        for i, silent in enumerate(is_silence):
            if silent and silence_start is None:
                silence_start = i
            elif not silent and silence_start is not None:
                duration = (i - silence_start) * frame_duration
                if duration >= min_silence_duration:
                    pauses += 1
                silence_start = None

        # Handle trailing silence
        if silence_start is not None:
            duration = (len(is_silence) - silence_start) * frame_duration
            if duration >= min_silence_duration:
                pauses += 1

        return pauses
    except Exception as e:
        logger.error(f"Pause detection error: {e}")
        return 0


# ---------------------------------------------------------------------------
# Helper: nervousness score
# ---------------------------------------------------------------------------

def compute_nervousness(filler_count: int, pause_count: int, speech_rate: float,
                        recovery_time: Optional[float] = None) -> float:
    """
    Nervousness score 0-100.
    Components:
      fillers  40%  (normalised, cap at 10)
      pauses   40%  (normalised, cap at 5)
      rate     20%  (deviation below ideal rate)
    Optional recovery_time penalty: up to +15 pts
    """
    filler_norm = min(filler_count / 10.0, 1.0)
    pause_norm = min(pause_count / 5.0, 1.0)
    rate_penalty = max(0.0, (IDEAL_SPEECH_RATE - speech_rate) / IDEAL_SPEECH_RATE)

    score = (filler_norm * 0.4 + pause_norm * 0.4 + rate_penalty * 0.2) * 100

    if recovery_time:
        recovery_penalty = min(recovery_time / 10.0, 1.0) * 15
        score = min(100, score + recovery_penalty)

    return round(score, 1)


# ---------------------------------------------------------------------------
# Helper: improvement tip
# ---------------------------------------------------------------------------

def generate_tip(filler_count: int, pause_count: int, speech_rate: float) -> str:
    tips = []
    if filler_count >= 3:
        tips.append(("fillers", filler_count,
                     f"You used {filler_count} filler word(s). Practice pausing silently instead of saying 'um' or 'uh'."))
    if pause_count >= 2:
        tips.append(("pauses", pause_count,
                     f"You had {pause_count} long pause(s). Prepare short bridging phrases like 'That's a great question—' to keep momentum."))
    if speech_rate < 1.5:
        tips.append(("rate", abs(IDEAL_SPEECH_RATE - speech_rate),
                     f"Your speech rate was slow ({speech_rate:.1f} w/s). Aim for 2–3 words per second to sound more confident."))
    if speech_rate > 3.5:
        tips.append(("rate_fast", abs(speech_rate - IDEAL_SPEECH_RATE),
                     f"You spoke quite fast ({speech_rate:.1f} w/s). Slow down and breathe—clarity beats speed."))

    if not tips:
        return "Great job! Your answer was clear and well-paced. Keep it up!"

    # Return tip for worst metric
    tips.sort(key=lambda x: -x[1])
    return tips[0][2]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/create_session")
def create_session(req: CreateSessionRequest, user_id: str = Depends(verify_jwt)):
    try:
        result = supabase.table("sessions").insert({
            "user_id": user_id,
            "company": req.company,
            "role": req.role,
            "round": req.round,
            "first_time": req.first_time,
            "distraction_enabled": req.distraction_enabled,
            "status": "in_progress",
        }).execute()
        session = result.data[0]
        return {"session_id": session["id"], "session": session}
    except Exception as e:
        logger.error(f"create_session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate_questions")
def generate_questions(req: GenerateQuestionsRequest, user_id: str = Depends(verify_jwt)):
    """Generate 5 interview questions using Groq LLM and store them."""
    first_time_text = "This is the candidate's first time applying for this type of role." if req.first_time else ""
    prompt = f"""You are an expert technical interviewer. Generate exactly 5 interview questions for:
- Company: {req.company}
- Role: {req.role}
- Interview Round: {req.round}
{first_time_text}

Requirements:
- Mix behavioral and technical questions appropriate for the round.
- Make them specific to the company/role where possible.
- Each question should be clear and concise (1–2 sentences).

Respond ONLY with a JSON array of 5 strings. No preamble, no markdown, no explanation.
Example: ["Question 1?", "Question 2?", "Question 3?", "Question 4?", "Question 5?"]"""

    try:
        response = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        raw = re.sub(r"```json|```", "", raw).strip()
        questions_list = json.loads(raw)
        if not isinstance(questions_list, list) or len(questions_list) < 5:
            raise ValueError("Invalid questions format from LLM")

        # Store questions in DB
        rows = [
            {
                "session_id": req.session_id,
                "question_text": q,
                "order_index": i,
            }
            for i, q in enumerate(questions_list[:5])
        ]
        result = supabase.table("questions").insert(rows).execute()
        return {"questions": result.data}
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}, raw: {raw}")
        # Fallback: generic questions
        fallback = [
            f"Tell me about your experience relevant to the {req.role} role.",
            "Describe a challenging project you worked on and how you overcame obstacles.",
            "Where do you see yourself in 5 years?",
            f"What specifically interests you about working at {req.company}?",
            "Do you have any questions for us?",
        ]
        rows = [{"session_id": req.session_id, "question_text": q, "order_index": i}
                for i, q in enumerate(fallback)]
        result = supabase.table("questions").insert(rows).execute()
        return {"questions": result.data}
    except Exception as e:
        logger.error(f"generate_questions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze_answer")
async def analyze_answer(
    session_id: str = Form(...),
    question_id: str = Form(...),
    recovery_time: Optional[float] = Form(None),
    audio: UploadFile = File(...),
    user_id: str = Depends(verify_jwt),
):
    """Transcribe audio, analyse metrics, store answer, return results."""
    suffix = Path(audio.filename).suffix if audio.filename else ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
        # 1. Transcribe with faster-whisper
        segments, info = whisper_model.transcribe(tmp_path, beam_size=3)
        transcript = " ".join(seg.text for seg in segments).strip()
        duration = info.duration or 1.0

        # 2. Filler words
        filler_count = count_fillers(transcript)

        # 3. Long pauses
        pause_count = count_long_pauses(tmp_path)

        # 4. Speech rate (words per second)
        word_count = len(transcript.split())
        speech_rate = round(word_count / max(duration, 1.0), 2)

        # 5. Nervousness score
        nervousness = compute_nervousness(filler_count, pause_count, speech_rate, recovery_time)

        # 6. Improvement tip
        tip = generate_tip(filler_count, pause_count, speech_rate)

        # 7. Store in DB
        answer_row = {
            "session_id": session_id,
            "question_id": question_id,
            "transcript": transcript,
            "filler_count": filler_count,
            "pause_count": pause_count,
            "speech_rate": speech_rate,
            "nervousness_score": nervousness,
            "improvement_tip": tip,
            "recovery_time": recovery_time,
        }
        result = supabase.table("answers").insert(answer_row).execute()
        answer = result.data[0]

        return {
            "answer_id": answer["id"],
            "transcript": transcript,
            "filler_count": filler_count,
            "pause_count": pause_count,
            "speech_rate": speech_rate,
            "nervousness_score": nervousness,
            "improvement_tip": tip,
            "duration": round(duration, 1),
        }
    finally:
        os.unlink(tmp_path)


@app.get("/get_session/{session_id}")
def get_session(session_id: str, user_id: str = Depends(verify_jwt)):
    """Fetch a session with all questions and answers."""
    try:
        session = supabase.table("sessions").select("*").eq("id", session_id).single().execute()
        questions = (supabase.table("questions")
                     .select("*")
                     .eq("session_id", session_id)
                     .order("order_index")
                     .execute())
        answers = (supabase.table("answers")
                   .select("*")
                   .eq("session_id", session_id)
                   .execute())
        return {
            "session": session.data,
            "questions": questions.data,
            "answers": answers.data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard")
def dashboard(user_id: str = Depends(verify_jwt)):
    """Return all sessions for the authenticated user."""
    try:
        sessions = (supabase.table("sessions")
                    .select("*")
                    .eq("user_id", user_id)
                    .order("created_at", desc=True)
                    .execute())
        return {"sessions": sessions.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/save_session")
def save_session(req: SaveSessionRequest, user_id: str = Depends(verify_jwt)):
    """Mark session as completed and compute overall nervousness."""
    try:
        answers = (supabase.table("answers")
                   .select("nervousness_score")
                   .eq("session_id", req.session_id)
                   .execute())
        scores = [a["nervousness_score"] for a in answers.data if a["nervousness_score"] is not None]
        overall = round(sum(scores) / len(scores), 1) if scores else 0.0

        supabase.table("sessions").update({
            "status": "completed",
            "overall_nervousness": overall,
        }).eq("id", req.session_id).execute()

        return {"status": "completed", "overall_nervousness": overall}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate_improvement_plan")
def generate_improvement_plan(req: dict, user_id: str = Depends(verify_jwt)):
    """Generate a personalised improvement plan using Groq."""
    session_id = req.get("session_id")
    try:
        answers = (supabase.table("answers")
                   .select("filler_count,pause_count,speech_rate,nervousness_score,improvement_tip")
                   .eq("session_id", session_id)
                   .execute())
        data = answers.data
        if not data:
            return {"plan": "No answers found for this session."}

        avg_fillers = sum(a["filler_count"] or 0 for a in data) / len(data)
        avg_pauses = sum(a["pause_count"] or 0 for a in data) / len(data)
        avg_rate = sum(a["speech_rate"] or 0 for a in data) / len(data)
        avg_score = sum(a["nervousness_score"] or 0 for a in data) / len(data)

        prompt = f"""You are an interview coach. Based on the following performance metrics from a mock interview session, write a concise, actionable improvement plan.

Metrics:
- Average filler words per answer: {avg_fillers:.1f}
- Average long pauses per answer: {avg_pauses:.1f}
- Average speech rate: {avg_rate:.1f} words/second (ideal: 2.5)
- Overall nervousness score: {avg_score:.1f}/100

Write a 3-part plan:
1. **Key Weakness**: The single biggest area to improve.
2. **Daily Drill**: A specific 5-minute daily exercise to fix it.
3. **Next Session Target**: A measurable goal for the next practice session.

Keep it encouraging, specific, and under 200 words."""

        response = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=400,
        )
        plan = response.choices[0].message.content.strip()
        return {"plan": plan}
    except Exception as e:
        logger.error(f"generate_improvement_plan error: {e}")
        return {"plan": "Focus on reducing filler words, controlling your pace, and practising smooth transitions between points."}
