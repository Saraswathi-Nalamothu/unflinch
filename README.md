markdown
# 🎙️ Unflinch – AI Interview Prep Assistant

**Unflinch** is an AI-powered interview preparation tool that listens to your answers, analyzes filler words ("um", "uh", "like"), long pauses, and speech rate, then gives personalized feedback. It includes a **Distraction Mode** that throws surprise questions to test your composure under real pressure.

> Built with React (Vite), FastAPI, Supabase, Groq LLM, Faster‑Whisper, and deployed on Vercel + Render.

---

## ✨ Features

- 🔐 **Authentication** – Email/Password + Google Sign‑In (powered by Supabase)
- 📊 **Dashboard** – Session history with nervousness trend chart
- 🎤 **Voice recording & analysis** – Real‑time transcription (Whisper), filler word & pause detection, speech rate calculation
- 🎯 **Nervousness score** – 0–100 gauge based on fillers, pauses, and speed
- 💡 **Per‑question improvement tips** – Actionable advice after each answer
- 🌀 **Distraction Mode** – Random surprise questions during an answer, recovery time tracking
- 📈 **Final improvement plan** – Custom drill + next session target
- 🌙 **Dark mode** – Persistent user preference
- 📱 **Mobile‑first responsive design**

---

## 🧰 Tech Stack

| Layer | Tools |
|-------|-------|
| **Frontend** | React + Vite, Tailwind CSS, shadcn/ui, Recharts |
| **Backend** | FastAPI (Python), Uvicorn |
| **Auth & Database** | Supabase (PostgreSQL, Row Level Security) |
| **AI / ML** | Groq (Llama 3 for question generation), Faster‑Whisper (speech‑to‑text), Librosa (audio analysis) |
| **Deployment** | Vercel (frontend), Render (backend) |

---

## 🚀 Live Demo

- **Frontend (Vercel):** `https://unflinch.vercel.app` *(replace with your actual URL)*
- **Backend (Render):** `https://unflinch.onrender.com` *(replace with your actual URL)*

---

## 🛠️ Local Development Setup

### Prerequisites

- Node.js 18+ & npm
- Python 3.10+
- Supabase account (free tier)
- Groq API key (free from [console.groq.com](https://console.groq.com))

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/unflinch.git
cd unflinch
2. Frontend setup
bash
cd frontend
npm install
cp .env.example .env   # or create .env manually
.env (Vite prefix required):

env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your_anon_key
Run dev server:

bash
npm run dev
3. Backend setup
bash
cd ../backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
.env (in backend/):

env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
GROQ_API_KEY=your_groq_key
Run backend:

bash
uvicorn main:app --reload --port 8000
4. Supabase configuration
Create a Supabase project

Enable Email provider (disable email confirmation for development)

Enable Google provider (optional)

Run the SQL schema (see supabase/schema.sql in the repo)

Set up Row Level Security (RLS) policies for sessions, questions, answers tables

📦 Deployment
Frontend (Vercel)
Push code to GitHub

Import repo in Vercel

Add environment variables: VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY

Deploy – auto‑redeploys on push

Backend (Render)
Push backend code to GitHub

Create a Web Service on Render

Build command: pip install -r requirements.txt

Start command: uvicorn main:app --host 0.0.0.0 --port $PORT

Add environment variables: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GROQ_API_KEY

🧪 Testing the App
Open frontend URL → Sign up with email/password or Google

On Dashboard → Start New Interview

Fill company, role, round, enable Distraction Mode (optional)

Answer 5 questions – record your voice each time

After recording, see instant metrics (fillers, pauses, nervousness score) + tip

After last question → Summary page with final improvement plan

Check Dashboard history – sessions are saved in Supabase

🗂️ Database Schema (Supabase)
profiles – extends auth.users

sessions – stores each interview (company, role, round, distraction mode, overall score)

questions – per‑session questions

answers – per‑answer transcript, filler_count, pause_count, speech_rate, nervousness_score, improvement_tip, recovery_time (for distraction mode)

RLS enabled: users can only read/write their own data.

📝 Known Issues & Workarounds
Whisper model download on Render – The free tier may time out. Fix: pre‑download the model during build or use a smaller tiny model.

Audio format – Use WebM/Opus from MediaRecorder. Backend may need pydub + ffmpeg for conversion.

CORS – Ensure backend allows https://your-vercel-app.vercel.app in CORSMiddleware.

🤝 Contributing
This is a personal portfolio project, but feel free to fork and improve. PRs are welcome.
