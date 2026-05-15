# 🎯 Unflinch — AI Interview Prep Assistant

> Voice-analysed mock interviews with real-time nervousness scoring, distraction training, and AI-powered improvement plans.

---

## Tech Stack

| Layer      | Technology                                  |
|------------|---------------------------------------------|
| Frontend   | React 18 + Vite + Tailwind CSS              |
| Backend    | FastAPI (Python 3.10+)                      |
| Database   | Supabase (PostgreSQL + Auth)                |
| STT        | faster-whisper (runs locally, no API key)   |
| LLM        | Groq API (Llama 3, free tier)               |
| Audio      | librosa (pause detection)                   |
| Deploy     | Vercel (frontend) + Render (backend)        |

---

## Project Structure

```
unflinch/
├── backend/
│   ├── main.py              # FastAPI app — all endpoints
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── package.json
│   ├── .env.example
│   └── src/
│       ├── main.jsx
│       ├── App.jsx          # Router
│       ├── index.css
│       ├── lib/
│       │   ├── supabase.js  # Supabase client
│       │   └── api.js       # Backend API client
│       ├── hooks/
│       │   ├── useAuth.js   # Auth state hook
│       │   └── useRecorder.js # MediaRecorder hook
│       ├── components/
│       │   └── UI.jsx       # Shared UI components
│       └── pages/
│           ├── AuthPage.jsx
│           ├── DashboardPage.jsx
│           ├── SetupPage.jsx
│           ├── InterviewPage.jsx
│           └── SummaryPage.jsx
└── supabase/
    └── migrations/
        └── 001_init.sql     # Database schema
```

---

## ① Supabase Setup

### 1. Create a project
- Go to https://supabase.com → New project
- Note your **Project URL** and **anon key** (Settings → API)
- Also copy the **service_role key** (keep secret — backend only)

### 2. Enable Phone OTP Auth
- Dashboard → Authentication → Providers → Phone
- Enable it. For testing use **Twilio** or **MessageBird** (Supabase has a free sandbox).
- For local dev you can enable "Disable phone confirmation" (Auth → Settings) and use any 6-digit code.

### 3. Run the migration
- Dashboard → SQL Editor → New query
- Paste the contents of `supabase/migrations/001_init.sql`
- Click **Run**

---

## ② Backend Setup

### Prerequisites
- Python 3.10+ 
- `ffmpeg` installed (needed by librosa/whisper for audio conversion):
  - macOS: `brew install ffmpeg`
  - Ubuntu: `sudo apt install ffmpeg`
  - Windows: https://ffmpeg.org/download.html

### Install

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env with your values:
# SUPABASE_URL=https://xxxx.supabase.co
# SUPABASE_SERVICE_ROLE_KEY=eyJ...
# GROQ_API_KEY=gsk_...
# WHISPER_MODEL_SIZE=base   (tiny=fast, base=better, small=best)
```

### Get a free Groq API key
- Sign up at https://console.groq.com
- Create an API key (free tier has generous limits)

### Run locally

```bash
uvicorn main:app --reload --port 8000
```

First run will download the Whisper model (~150MB for `base`). 
API docs available at http://localhost:8000/docs

---

## ③ Frontend Setup

### Install

```bash
cd frontend
npm install
```

### Configure

```bash
cp .env.example .env
# Edit .env:
# VITE_SUPABASE_URL=https://xxxx.supabase.co
# VITE_SUPABASE_ANON_KEY=eyJ...  (anon key, not service role)
# VITE_API_BASE_URL=http://localhost:8000
```

### Run locally

```bash
npm run dev
# Opens at http://localhost:3000
```

---

## ④ Deployment

### Backend → Render

1. Push `backend/` to a GitHub repo (or the whole monorepo)
2. Go to https://render.com → New Web Service
3. Connect your repo, set root directory to `backend/`
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables in the Render dashboard
7. Instance type: **Free** works for testing; upgrade for production

> **Note**: Render free tier sleeps after inactivity. Use the paid tier for always-on.

> **Note on Whisper**: The model downloads on first startup (~150MB). This takes a minute. Use `WHISPER_MODEL_SIZE=tiny` for faster cold starts on free tier.

### Frontend → Vercel

1. Push `frontend/` to GitHub
2. Go to https://vercel.com → New Project → Import repo
3. Framework: **Vite**
4. Root directory: `frontend/`
5. Add env vars:
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY`  
   - `VITE_API_BASE_URL` = your Render backend URL (e.g. `https://unflinch-api.onrender.com`)
6. Deploy

### CORS (Production)
Update `main.py` to allow your Vercel domain:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-app.vercel.app"],
    ...
)
```

---

## API Endpoints

| Method | Path                        | Auth | Description                         |
|--------|-----------------------------|------|-------------------------------------|
| GET    | `/health`                   | No   | Health check                        |
| POST   | `/create_session`           | JWT  | Create interview session             |
| POST   | `/generate_questions`       | JWT  | Generate 5 AI questions             |
| POST   | `/analyze_answer`           | JWT  | Transcribe + analyse audio answer   |
| GET    | `/get_session/{id}`         | JWT  | Fetch session + questions + answers |
| GET    | `/dashboard`                | JWT  | All sessions for current user       |
| POST   | `/save_session`             | JWT  | Mark session complete                |
| POST   | `/generate_improvement_plan`| JWT  | AI improvement plan for session     |

All authenticated endpoints require `Authorization: Bearer <supabase_jwt>` header.

---

## Nervousness Score Formula

```
nervousness = (
    min(filler_count / 10, 1.0)  × 40%  +
    min(pause_count  /  5, 1.0)  × 40%  +
    max(0, (2.5 - speech_rate) / 2.5)   × 20%
) × 100

Optional: +15pt penalty for distraction recovery time
```

- **0–34**: Calm & confident 🟢
- **35–59**: Moderate nerves 🟡  
- **60–100**: High nervousness 🔴

---

## Features Checklist

- [x] Phone OTP authentication (Supabase)
- [x] Dashboard with session history + nervousness trend chart
- [x] AI question generation (Groq + Llama 3)
- [x] Browser audio recording (MediaRecorder API)
- [x] Speech-to-text (faster-whisper, local)
- [x] Filler word detection (regex)
- [x] Long pause detection (librosa)
- [x] Speech rate calculation
- [x] Nervousness score (weighted formula)
- [x] Per-answer improvement tips
- [x] Distraction Mode (surprise interruptions)
- [x] Session summary with Q&A breakdown
- [x] AI improvement plan (Groq)
- [x] PDF report download (jsPDF)
- [x] Row-level security on all Supabase tables
- [x] JWT verification on all backend endpoints

---

## Troubleshooting

**"Microphone access denied"**  
→ Allow microphone in browser settings. Chrome: click the 🔒 icon in address bar.

**Audio transcription is slow**  
→ Use `WHISPER_MODEL_SIZE=tiny` for speed. `base` is the default balance.

**"Invalid or expired token"**  
→ Supabase JWTs expire after 1 hour by default. The frontend auto-refreshes; just reload if needed.

**ffmpeg not found**  
→ Install ffmpeg and ensure it's in your PATH: `which ffmpeg` / `ffmpeg -version`

**Questions are generic**  
→ Check your `GROQ_API_KEY` is set. The fallback to generic questions means Groq isn't responding.
