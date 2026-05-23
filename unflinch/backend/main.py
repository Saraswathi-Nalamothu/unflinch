"""
Unflinch – AI Interview Prep Assistant
FastAPI Backend – Final working version
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

app = FastAPI(title="Unflinch API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FILLER_WORDS = [
    "um","uh","like","so","actually","basically",
    "you know","right","well","kinda","kind of"
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

    for filler in FILLER_WORDS:
        pattern = r"\b" + re.escape(filler) + r"\b"
        count += len(re.findall(pattern, text_lower))

    return count

def count_long_pauses(audio_path: str,
                      min_silence_duration: float = 1.5,
                      silence_threshold_db: float = -40.0) -> int:
    try:
        y, sr = librosa.load(audio_path, sr=None, mono=True)

        rms = librosa.feature.rms(
            y=y,
            frame_length=2048,
            hop_length=512
        )[0]

        db = librosa.amplitude_to_db(rms, ref=np.max)

        frame_duration = 512 / sr

        is_silence = db < silence_threshold_db

        pauses = 0
        silence_start = None

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

def is_silent_audio(audio_path: str,
                    silence_threshold_db: float = -45.0) -> bool:
    try:
        y, sr = librosa.load(audio_path, sr=None, mono=True)

        rms = librosa.feature.rms(y=y)[0]

        db = librosa.amplitude_to_db(rms, ref=np.max)

        silent_ratio = np.sum(db < silence_threshold_db) / len(db)

        return silent_ratio > 0.90

    except:
        return False

def compute_nervousness(filler_count,
                        pause_count,
                        speech_rate,
                        recovery_time=None):

    filler_norm  = min(filler_count / 10.0, 1.0)
    pause_norm   = min(pause_count  /  5.0, 1.0)

    rate_penalty = max(
        0.0,
        (IDEAL_SPEECH_RATE - speech_rate) / IDEAL_SPEECH_RATE
    )

    score = (
        filler_norm * 0.4
        + pause_norm * 0.4
        + rate_penalty * 0.2
    ) * 100

    if recovery_time:
        score = min(
            100,
            score + min(recovery_time / 10.0, 1.0) * 15
        )

    return round(score, 1)

def voice_tip(filler_count, pause_count, speech_rate):

    tips = []

    if filler_count >= 3:
        tips.append((
            filler_count,
            f"You used {filler_count} filler word(s). Pause silently instead of saying 'um' or 'uh'."
        ))

    if pause_count >= 2:
        tips.append((
            pause_count,
            f"You had {pause_count} long pause(s). Use bridging phrases to stay fluid."
        ))

    if speech_rate < 1.5:
        tips.append((
            5,
            f"You spoke slowly ({speech_rate:.1f} w/s). Aim for 2-3 words/second."
        ))

    if speech_rate > 3.5:
        tips.append((
            4,
            f"You spoke very fast ({speech_rate:.1f} w/s). Slow down for clarity."
        ))

    if not tips:
        return "Great delivery! Keep that pace and clarity."

    tips.sort(key=lambda x: -x[0])

    return tips[0][1]

def ai_analyze_answer(question_text,
                      transcript,
                      filler_count,
                      pause_count,
                      speech_rate):

    no_answer_phrases = [
        "i don't know",
        "i dont know",
        "i have no idea",
        "not sure",
        "i'm not sure",
        "im not sure",
        "i cannot answer",
        "sorry i don't",
        "sorry i dont",
        "no idea",
    ]

    transcript_lower = transcript.lower().strip()

    is_blank = (
        any(p in transcript_lower for p in no_answer_phrases)
        or len(transcript.split()) < 8
    )

    if is_blank:

        prompt = f"""
Interview question: "{question_text}"
Candidate said: "{transcript}"
They didn't know the answer. Teach them briefly.

JSON only (no markdown):
{{"content_feedback":"Why this question matters (1 sentence).","better_answer":"Model answer in first person (3-4 sentences).","voice_feedback":"One delivery tip.","overall_tip":"One action to prepare this answer."}}
"""

    else:

        prompt = f"""
Question: "{question_text}"
Answer: "{transcript}"
Metrics: {filler_count} fillers, {pause_count} pauses, {speech_rate:.1f}w/s rate.

JSON only (no markdown):
{{"content_feedback":"What was good and what was missing (2 sentences).","better_answer":"Improved version in first person (3-4 sentences).","voice_feedback":"One delivery tip based on metrics.","overall_tip":"Single most important improvement."}}
"""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role":"system",
                    "content":"Interview coach. JSON only, no markdown."
                },
                {
                    "role":"user",
                    "content":prompt
                }
            ],
            temperature=0.4,
            max_tokens=400,
        )

        raw = re.sub(
            r"```json|```",
            "",
            response.choices[0].message.content.strip()
        ).strip()

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
            "voice_feedback":   voice_tip(
                filler_count,
                pause_count,
                speech_rate
            ),
            "overall_tip":      voice_tip(
                filler_count,
                pause_count,
                speech_rate
            ),
        }

@app.get("/health")
def health():
    return {
        "status": "ok",
        "cors": "enabled"
    }