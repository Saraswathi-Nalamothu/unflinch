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
    allow_credentials=False,
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
    "Friendly": "You are warm and encouraging. You rephrase if the candidate seems stuck. Your questions are clear and supportive.",
    "Neutral": "You are professional and objective. Standard pacing.",
    "Tough": "You are skeptical. You challenge vague answers. You ask 'Why?' and 'Can you be more specific?' often.",
    "Stress Test": "You are deliberately intimidating. You interrupt with harder follow-ups. You question the candidate's assumptions. You say things like 'Our last candidate answered that differently.'",
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
    persona: str = "Neutral"

class SaveSessionRequest(BaseModel):
    session_id: str

class CreateSessionRequest(BaseModel):
    company: str
    role: str
    round: str
    first_time: bool
    distraction_enabled: bool
    persona: str = "Neutral"

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

def ai_analyze_answer(question_text, transcript, filler_count, pause_count, speech_rate, role, company, rnd, persona):
    prompt = f"""You are evaluating a {role} candidate at {company} in a {rnd} interview.

Question asked: "{question_text}"
Candidate transcript: "{transcript}"

Analyze strictly as a real interviewer would. Return ONLY this JSON:
{{
  "filler_count": {filler_count},
  "pause_count": {pause_count},
  "speech_rate": {speech_rate},
  "nervousness_score": <int 0-100, higher = more nervous>,
  "confidence_score": <int 0-100>,
  "clarity_score": <int 0-100, how clear and structured the answer was>,
  "relevance_score": <int 0-100, how well answer matched the question>,
  "structure_score": <int 0-100, did they use STAR or clear framework>,
  "advice": "<one sharp, specific, actionable tip for THIS answer>",
  "what_worked": "<one thing they did well in this specific answer>",
  "red_flag": "<one thing that would concern a real interviewer, or null>"
}}

Be strict. A mediocre answer should score 55-65, not 80+.
Penalize vague answers, lack of examples, excessive fillers.
Reward specific metrics, structured thinking, confident delivery."""

    persona_style = PERSONA_STYLES.get(persona, PERSONA_STYLES["Neutral"])

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": f"You are an expert interviewer. {persona_style} Respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            raw = match.group()
        parsed = json.loads(raw)
        
        # Parse challenge question if needed
        challenge = None
        if persona in ["Tough", "Stress Test"]:
            c_prompt = f"""The candidate just answered: "{transcript}"
To the question: "{question_text}"
As a {persona} interviewer at {company}, generate ONE sharp follow-up challenge or pushback question. Under 25 words. Return only the question string."""
            c_res = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": c_prompt}],
                temperature=0.7, max_tokens=100
            )
            challenge = c_res.choices[0].message.content.strip().replace('"', '')

        return {
            "nervousness_score": parsed.get("nervousness_score", 50),
            "confidence_score": parsed.get("confidence_score", 50),
            "clarity_score": parsed.get("clarity_score", 50),
            "relevance_score": parsed.get("relevance_score", 50),
            "structure_score": parsed.get("structure_score", 50),
            "advice": parsed.get("advice", "Practice your delivery."),
            "what_worked": parsed.get("what_worked", "Good effort."),
            "red_flag": parsed.get("red_flag", None),
            "challenge_question": challenge
        }
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        return {
            "nervousness_score": 50, "confidence_score": 50, "clarity_score": 50,
            "relevance_score": 50, "structure_score": 50,
            "advice": "Could not analyze answer.", "what_worked": "N/A", "red_flag": None, "challenge_question": None
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
            "persona":req.persona
        }).execute()
        return {"session_id":result.data[0]["id"],"session":result.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_questions")
def generate_questions(req: GenerateQuestionsRequest, user_id: str = Depends(verify_jwt)):
    persona_style = PERSONA_STYLES.get(req.persona, PERSONA_STYLES["Neutral"])

    # 1. Fetch Company Context
    context_prompt = f"""In 5 bullet points, what should a {req.role} candidate know about {req.company} before their interview? Include: known interview style, culture keywords, tech stack if relevant, a recent product or initiative, and one thing interviewers commonly assess there. Return as a JSON array of exactly 5 strings. No markdown, no explanation, only the JSON array."""
    session_context = []
    try:
        ctx_res = groq_client.chat.completions.create(
            model=GROQ_MODEL_QUALITY,
            messages=[{"role":"user","content":context_prompt}],
            temperature=0.5, max_tokens=400,
        )
        raw_ctx = re.sub(r"```json|```","",ctx_res.choices[0].message.content.strip()).strip()
        match = re.search(r'\[[\s\S]*\]', raw_ctx)
        if match: raw_ctx = match.group()
        session_context = json.loads(raw_ctx)
        supabase.table("sessions").update({"session_context": session_context}).eq("id", req.session_id).execute()
    except Exception as e:
        logger.error(f"Context error: {e}")
        session_context = [f"Understand {req.company}'s core values.", f"Know the general expectations for a {req.role}.", "Be ready for behavioral questions.", "Research recent news about the company.", "Understand the industry landscape."]

    # 2. Generate First Question Only
    system_prompt = f"""You are a senior interviewer at {req.company}. You have deep knowledge of {req.company}'s culture, hiring bar, known interview style, tech stack (if applicable), and the specific expectations for a {req.role} in a {req.round} interview.
{persona_style}"""

    q_counts = {"First Round": 4, "Technical": 6, "HR": 5, "Final": 7, "Final Round": 7, "Case Study": 3}
    q_count = q_counts.get(req.round, 5)

    user_prompt = f"""Generate the VERY FIRST question for a realistic, sequential interview for {req.role} at {req.company}, {req.round} round.

COMPANY-AWARE RULES:
- If company is Google: reference Googleyness or scale.
- If company is Amazon: reference a Leadership Principle.
- If company is a startup: focus on ownership and execution.
- For any company: research what they are publicly known for and weave it in naturally.

CRITICAL RULE: DO NOT assume the candidate has worked at {req.company} before. Ask about their past experience that prepares them for this role at {req.company}. For example, instead of "tell me about your time at {req.company}", ask "tell me about a time in your previous roles that prepared you for {req.company}".

Company context: {json.dumps(session_context)}

Return ONLY a JSON array containing exactly ONE question string. No explanation, no numbering, no markdown fences.
["Question string here"]"""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL_QUALITY,
            messages=[
                {"role":"system","content":system_prompt},
                {"role":"user","content":user_prompt}
            ],
            temperature=0.7, max_tokens=200,
        )
        raw = re.sub(r"```json|```","",response.choices[0].message.content.strip()).strip()
        match = re.search(r'\[[\s\S]*\]', raw)
        if match:
            raw = match.group()
        questions_list = json.loads(raw)
        if not isinstance(questions_list,list) or len(questions_list) < 1:
            raise ValueError("Invalid format")
        
        q_text = questions_list[0]
    except Exception as e:
        logger.error(f"generate_questions error: {e}")
        q_text = f"Tell me about a relevant experience in your past roles that prepares you for the {req.role} role at {req.company}."

    rows = [{"session_id": req.session_id, "question_text": q_text, "order_index": 0}]
    result = supabase.table("questions").insert(rows).execute()
    return {"questions": result.data, "target_questions": q_count}

@app.post("/analyze_answer")
async def analyze_answer(
    session_id:    str             = Form(...),
    question_id:   str             = Form(...),
    question_text: str             = Form(""),
    recovery_time: Optional[float] = Form(None),
    hint_used:     bool            = Form(False),
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
        session_data = supabase.table("sessions").select("role,company,round,persona").eq("id",session_id).single().execute().data
        role = session_data["role"]
        company = session_data["company"]
        rnd = session_data["round"]
        persona = session_data.get("persona", "Neutral")

        ai_feedback      = ai_analyze_answer(
            question_text or "Interview question",
            transcript, filler_count, pause_count, speech_rate, role, company, rnd, persona
        )
        tip = ai_feedback["advice"]

        result = supabase.table("answers").insert({
            "session_id":session_id,"question_id":question_id,
            "transcript":transcript,"filler_count":filler_count,
            "pause_count":pause_count,"speech_rate":speech_rate,
            "nervousness_score":ai_feedback["nervousness_score"],
            "confidence_score":ai_feedback["confidence_score"],
            "clarity_score":ai_feedback["clarity_score"],
            "relevance_score":ai_feedback["relevance_score"],
            "structure_score":ai_feedback["structure_score"],
            "improvement_tip":tip,
            "what_worked":ai_feedback["what_worked"],
            "red_flag":ai_feedback["red_flag"],
            "challenge_question":ai_feedback["challenge_question"],
            "recovery_time":recovery_time,
            "hint_used":hint_used,
        }).execute()

        # Generate next question if not at the end
        q_counts = {"First Round": 4, "Technical": 6, "HR": 5, "Final": 7, "Final Round": 7, "Case Study": 3}
        q_count = q_counts.get(rnd, 5)
        
        current_qs = supabase.table("questions").select("id").eq("session_id", session_id).execute().data
        next_q_data = None
        
        if len(current_qs) < q_count:
            # Generate next question dynamically
            persona_style = PERSONA_STYLES.get(persona, PERSONA_STYLES["Neutral"])
            context = session_data.get("session_context", [])
            
            prompt = f"""You are a senior {persona} interviewer at {company} conducting a {rnd} interview for a {role} candidate.
The candidate was just asked: "{question_text}"
The candidate answered: "{transcript}"

Generate ONE realistic, conversational follow-up question based on their answer.
If they mentioned a specific project, metric, or challenge, ask about it.
If they were vague, ask for an example.
If this is the end of a topic, pivot to the next relevant area for a {role}.
Do NOT say 'Good answer' or 'Thank you', just ask the question directly as if in a real conversation.
{persona_style}

Company context: {json.dumps(context)}

Return ONLY the question string, nothing else."""

            try:
                nxt_res = groq_client.chat.completions.create(
                    model=GROQ_MODEL_QUALITY,
                    messages=[{"role":"user","content":prompt}],
                    temperature=0.7, max_tokens=150
                )
                next_q_text = nxt_res.choices[0].message.content.strip().replace('"', '')
                
                rows = [{"session_id": session_id, "question_text": next_q_text, "order_index": len(current_qs)}]
                q_result = supabase.table("questions").insert(rows).execute()
                next_q_data = q_result.data[0] if q_result.data else None
            except Exception as e:
                logger.error(f"Follow-up gen error: {e}")
                # Fallback to a generic follow-up
                next_q_text = f"Can you elaborate a bit more on that, keeping the {role} context in mind?"
                rows = [{"session_id": session_id, "question_text": next_q_text, "order_index": len(current_qs)}]
                q_result = supabase.table("questions").insert(rows).execute()
                next_q_data = q_result.data[0] if q_result.data else None

        return {
            "answer_id":result.data[0]["id"],"transcript":transcript,
            "filler_count":filler_count,"pause_count":pause_count,
            "speech_rate":speech_rate,"nervousness_score":ai_feedback["nervousness_score"],
            "confidence_score":ai_feedback["confidence_score"],
            "clarity_score":ai_feedback["clarity_score"],
            "relevance_score":ai_feedback["relevance_score"],
            "structure_score":ai_feedback["structure_score"],
            "improvement_tip":tip,"duration":round(duration,1),
            "what_worked":ai_feedback["what_worked"],
            "red_flag":ai_feedback["red_flag"],
            "challenge_question":ai_feedback["challenge_question"],
            "no_speech":False,
            "next_question": next_q_data,
        }
    finally:
        os.unlink(tmp_path)

@app.get("/get_session/{session_id}")
def get_session(session_id: str, user_id: str = Depends(verify_jwt)):
    try:
        session   = supabase.table("sessions").select("*").eq("id",session_id).single().execute()
        questions = supabase.table("questions").select("*").eq("session_id",session_id).order("order_index").execute()
        answers   = supabase.table("answers").select("*").eq("session_id",session_id).execute()
        
        q_counts = {"First Round": 4, "Technical": 6, "HR": 5, "Final": 7, "Final Round": 7, "Case Study": 3}
        target_questions = q_counts.get(session.data["round"], 5) if session.data else 5
        
        return {"session":session.data,"questions":questions.data,"answers":answers.data,"target_questions":target_questions}
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
        session_data = supabase.table("sessions").select("role,company,round,session_context").eq("id",session_id).single().execute().data
        
        questions = supabase.table("questions").select("id,question_text").eq("session_id",session_id).order("order_index").execute().data
        answers = supabase.table("answers").select(
            "question_id,nervousness_score,confidence_score,clarity_score,relevance_score,structure_score,improvement_tip,red_flag"
        ).eq("session_id",session_id).execute().data
        
        if not answers: return {"plan": "No answers found for this session."}
        
        q_json = json.dumps([q["question_text"] for q in questions])
        scores_json = json.dumps([{
            "question_id": a["question_id"],
            "nervousness": a["nervousness_score"],
            "confidence": a["confidence_score"],
            "clarity": a["clarity_score"],
            "relevance": a["relevance_score"],
            "structure": a["structure_score"]
        } for a in answers])
        advice_json = json.dumps([{ "question_id": a["question_id"], "advice": a["improvement_tip"] } for a in answers])
        flags_json = json.dumps([{ "question_id": a["question_id"], "red_flag": a["red_flag"] } for a in answers if a["red_flag"]])
        
        prompt = f"""You just finished evaluating a complete {session_data['round']} interview for {session_data['role']} at {session_data['company']}.

Here is the full session data:
Questions: {q_json}
Per-question scores: {scores_json}
Per-question advice: {advice_json}
Red flags: {flags_json}

Generate a personalized improvement plan. Return ONLY this JSON:
{{
  "overall_verdict": "<2 sentences: honest overall assessment of readiness for THIS role at THIS company>",
  "top_strengths": ["<strength 1>", "<strength 2>"],
  "critical_gaps": ["<gap 1>", "<gap 2>", "<gap 3>"],
  "weekly_plan": [
    {{
      "week": 1,
      "focus": "<skill/area>",
      "action": "<specific daily practice, under 20 words>"
    }},
    {{
      "week": 2,
      "focus": "<skill/area>",
      "action": "<specific daily practice>"
    }},
    {{
      "week": 3,
      "focus": "<skill/area>",
      "action": "<specific daily practice>"
    }}
  ],
  "company_specific_tip": "<one tip specifically about how {session_data['company']} evaluates candidates that this person should know>"
}}"""

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role":"user","content":prompt}],
            temperature=0.5, max_tokens=1000,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        match = re.search(r'\{[\s\S]*\}', raw)
        if match: raw = match.group()
        parsed = json.loads(raw)
        
        # Save to DB
        supabase.table("sessions").update({
            "overall_verdict": parsed.get("overall_verdict"),
            "weekly_plan": parsed.get("weekly_plan"),
            "company_specific_tip": parsed.get("company_specific_tip")
        }).eq("id", session_id).execute()
        
        return parsed
    except Exception as e:
        logger.error(f"improvement plan error: {e}")
        return {"overall_verdict":"Keep practicing! Focus on reducing fillers."}

@app.post("/generate_hint")
def generate_hint(req: dict, user_id: str = Depends(verify_jwt)):
    session_id = req.get("session_id")
    question_text = req.get("question_text")
    try:
        session_data = supabase.table("sessions").select("role,company,round").eq("id",session_id).single().execute().data
        
        prompt = f"""The candidate is stuck on this interview question:
"{question_text}"
Role: {session_data['role']}, Company: {session_data['company']}, Round: {session_data['round']}

Give a helpful hint that guides their thinking WITHOUT giving away the answer. Include:
1. What framework or structure to use (e.g. STAR, CIRCLES, first-principles)
2. One specific angle from their role/company context to consider
3. One thing to avoid

Return as plain text, conversational, under 60 words."""
        
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role":"user","content":prompt}],
            temperature=0.7, max_tokens=150,
        )
        hint = response.choices[0].message.content.strip()
        return {"hint": hint}

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role":"user","content":prompt}],
            temperature=0.5, max_tokens=400,
        )
        return {"plan":response.choices[0].message.content.strip()}
    except Exception as e:
        logger.error(f"improvement plan error: {e}")
        return {"plan":"You showed great effort in this session! Focus on reducing filler words by practising silent pauses, maintain your 2-3 w/s speech rate, and always include a specific example with measurable results in your answers."}