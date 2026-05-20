import React, { useState, useEffect, useRef } from 'react'
import { NavBar, Spinner, Toast, ScoreRing } from '../components/UI'
import { useRecorder } from '../hooks/useRecorder'
import { api } from '../lib/api'
import { supabase } from '../lib/supabase'
import { Zap, Mic, MicOff, ChevronRight, RotateCcw, CheckCircle } from 'lucide-react'

const DRILL_QUESTIONS = [
  "Tell me about yourself in 60 seconds.",
  "What's your biggest strength?",
  "Where do you see yourself in 3 years?",
  "Why should we hire you?",
  "What's your biggest weakness?",
  "Describe a time you showed leadership.",
  "How do you handle stress?",
  "What motivates you at work?",
  "Tell me about a failure and what you learned.",
  "Why are you looking for a new job?",
  "What makes you unique as a candidate?",
  "How do you prioritise tasks when everything is urgent?",
  "Describe your ideal work environment.",
  "Tell me about a time you disagreed with your manager.",
  "What's a skill you're currently developing?",
]

function shuffle(arr) {
  return [...arr].sort(() => Math.random() - 0.5)
}

function CountdownRing({ seconds, max = 60 }) {
  const r    = 40
  const circ = 2 * Math.PI * r
  const pct  = seconds / max
  const offset = circ - pct * circ
  const color  = seconds > 20 ? '#00E5A0' : seconds > 10 ? '#FF8C42' : '#FF4D1C'

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: 96, height: 96 }}>
      <svg width={96} height={96} viewBox="0 0 96 96">
        <circle cx="48" cy="48" r={r} fill="none" stroke="#2A2A3C" strokeWidth="6" />
        <circle
          cx="48" cy="48" r={r} fill="none"
          stroke={color} strokeWidth="6" strokeLinecap="round"
          strokeDasharray={circ} strokeDashoffset={offset}
          transform="rotate(-90 48 48)"
          style={{ transition: 'stroke-dashoffset 0.5s linear, stroke 0.3s' }}
        />
      </svg>
      <span className="absolute font-mono font-bold text-xl" style={{ color }}>{seconds}</span>
    </div>
  )
}

export default function QuickDrillPage({ navigate, onSignOut, user }) {
  const [phase, setPhase]       = useState('intro')   // intro | question | result | done
  const [questions, setQuestions] = useState([])
  const [idx, setIdx]           = useState(0)
  const [timeLeft, setTimeLeft] = useState(60)
  const [results, setResults]   = useState([])
  const [analysing, setAnalysing] = useState(false)
  const [currentResult, setCurrentResult] = useState(null)
  const [toast, setToast]       = useState(null)
  const [sessionId, setSessionId] = useState(null)

  const timerRef = useRef(null)
  const { recording, audioBlob, duration, error, start, stop, reset } = useRecorder(60)

  // Shuffle questions on mount
  useEffect(() => {
    setQuestions(shuffle(DRILL_QUESTIONS).slice(0, 5))
  }, [])

  // Countdown timer while recording
  useEffect(() => {
    if (recording) {
      setTimeLeft(60)
      timerRef.current = setInterval(() => {
        setTimeLeft(t => {
          if (t <= 1) { stop(); return 0 }
          return t - 1
        })
      }, 1000)
    } else {
      clearInterval(timerRef.current)
    }
    return () => clearInterval(timerRef.current)
  }, [recording])

  // Auto-submit when blob ready
  useEffect(() => {
    if (audioBlob) submitAnswer()
  }, [audioBlob])

  async function startDrill() {
    // Create a quick-drill session in Supabase
    try {
      const { data: { session: authSession } } = await supabase.auth.getSession()
      const token = authSession?.access_token
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/create_session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          company: 'Quick Drill', role: 'General', round: 'First Round',
          first_time: false, distraction_enabled: false,
        }),
      })
      const data = await res.json()
      setSessionId(data.session_id)

      // Insert questions
      const { data: { session: s2 } } = await supabase.auth.getSession()
      const t2 = s2?.access_token
      await fetch(`${import.meta.env.VITE_API_BASE_URL}/generate_questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${t2}` },
        body: JSON.stringify({
          session_id: data.session_id,
          company: 'Quick Drill', role: 'General Practice',
          round: 'First Round', first_time: false,
        }),
      })
    } catch (e) {
      // Continue without session — drill still works
    }
    setPhase('question')
  }

  async function submitAnswer() {
    if (!audioBlob || !questions[idx]) return
    setAnalysing(true)
    setCurrentResult(null)

    try {
      const fd = new FormData()
      fd.append('session_id', sessionId || 'drill')
      fd.append('question_id', 'drill-' + idx)
      fd.append('question_text', questions[idx])
      fd.append('audio', audioBlob, 'answer.webm')

      const { data: { session: authSession } } = await supabase.auth.getSession()
      const token = authSession?.access_token

      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/analyze_answer`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      })
      const data = await res.json()

      const wordCount = (data.transcript || '').trim().split(/\s+/).filter(Boolean).length
      if (wordCount < 3) {
        setCurrentResult({ noSpeech: true, question: questions[idx] })
      } else {
        const r = { ...data, question: questions[idx] }
        setCurrentResult(r)
        setResults(prev => [...prev, r])
      }
      setPhase('result')
    } catch (err) {
      setToast({ message: 'Analysis failed: ' + err.message, type: 'error' })
      setPhase('question')
    } finally {
      setAnalysing(false)
    }
  }

  function handleNext() {
    if (idx < questions.length - 1) {
      setIdx(i => i + 1)
      setCurrentResult(null)
      reset()
      setPhase('question')
    } else {
      setPhase('done')
    }
  }

  const avgScore = results.length
    ? results.reduce((a, b) => a + (b.nervousness_score || 0), 0) / results.length
    : 0

  // ── Intro ───────────────────────────────────────────────────
  if (phase === 'intro') return (
    <>
      <NavBar onSignOut={onSignOut} userName={user?.email} />
      <main className="min-h-screen bg-obsidian px-4 py-8 flex items-center justify-center">
        <div className="max-w-md w-full text-center animate-slide-up">
          <div className="w-16 h-16 bg-ember/10 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <Zap size={32} className="text-ember" />
          </div>
          <h1 className="heading-display text-5xl gradient-text mb-3">Quick Drill</h1>
          <p className="text-mist mb-2">5 rapid-fire questions. 60 seconds each.</p>
          <p className="text-mist/60 text-sm mb-8">Perfect daily warmup — no setup needed.</p>

          <div className="card mb-6 text-left">
            <p className="text-chalk text-sm font-medium mb-3">How it works:</p>
            <ul className="text-mist text-sm space-y-2">
              <li>🎯 You get 5 common interview questions</li>
              <li>🎙️ Record your answer (max 60 seconds)</li>
              <li>⚡ Get instant AI feedback on content + delivery</li>
              <li>📊 See your overall score at the end</li>
            </ul>
          </div>

          <div className="flex flex-col gap-3">
            <button className="btn-primary w-full flex items-center justify-center gap-2 py-4" onClick={startDrill}>
              <Zap size={18} /> Start Drill →
            </button>
            <button className="btn-ghost w-full" onClick={() => navigate('dashboard')}>
              ← Back to Dashboard
            </button>
          </div>
        </div>
      </main>
    </>
  )

  // ── Question ────────────────────────────────────────────────
  if (phase === 'question') return (
    <>
      <NavBar onSignOut={onSignOut} userName={user?.email} />
      <main className="min-h-screen bg-obsidian px-4 py-8">
        <div className="max-w-xl mx-auto">
          {/* Progress dots */}
          <div className="flex gap-2 justify-center mb-8">
            {questions.map((_, i) => (
              <div key={i} className={`w-2 h-2 rounded-full transition-all ${
                i < idx ? 'bg-ember' : i === idx ? 'bg-ember/60 scale-125' : 'bg-steel'}`} />
            ))}
          </div>

          <div className="text-center mb-2">
            <span className="text-mist text-xs font-mono uppercase tracking-widest">Question {idx + 1} of {questions.length}</span>
          </div>

          <div className="card mb-8 text-center">
            <div className="text-ember text-xs font-mono uppercase tracking-widest mb-3 flex items-center justify-center gap-1">
              <Zap size={12} /> Quick Drill
            </div>
            <p className="text-chalk text-xl md:text-2xl leading-relaxed">{questions[idx]}</p>
          </div>

          {analysing ? (
            <div className="flex flex-col items-center gap-4 py-8">
              <Spinner className="w-8 h-8 text-ember" />
              <p className="text-mist text-sm">Analysing…</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-6">
              {recording && <CountdownRing seconds={timeLeft} max={60} />}

              <div className="relative">
                {recording && (
                  <>
                    <div className="absolute inset-0 rounded-full bg-ember/30 sonar-ring" />
                    <div className="absolute inset-0 rounded-full bg-ember/20 sonar-ring-2" />
                  </>
                )}
                <button
                  onClick={recording ? stop : () => { reset(); start() }}
                  className={`relative w-20 h-20 rounded-full flex items-center justify-center
                    transition-all duration-200 active:scale-95 shadow-lg
                    ${recording ? 'bg-ember hover:bg-red-600' : 'bg-graphite border-2 border-steel hover:border-ember'}`}
                >
                  {recording ? <MicOff size={28} className="text-white" /> : <Mic size={28} className="text-chalk" />}
                </button>
              </div>

              <p className="text-mist text-sm">
                {recording ? 'Recording… click to stop' : 'Click mic to record (max 60s)'}
              </p>

              {!recording && (
                <button className="text-mist text-xs hover:text-chalk underline" onClick={handleNext}>
                  Skip this question →
                </button>
              )}
            </div>
          )}
        </div>
      </main>
    </>
  )

  // ── Result ──────────────────────────────────────────────────
  if (phase === 'result') return (
    <>
      <NavBar onSignOut={onSignOut} userName={user?.email} />
      <main className="min-h-screen bg-obsidian px-4 py-8">
        <div className="max-w-xl mx-auto animate-slide-up">
          <p className="text-mist text-xs font-mono uppercase tracking-widest text-center mb-6">
            Question {idx + 1} of {questions.length}
          </p>

          {currentResult?.noSpeech ? (
            <div className="card border-amber/40 bg-carbon text-center mb-6">
              <p className="text-amber font-semibold mb-2">No speech detected</p>
              <p className="text-mist text-sm">Check your mic and try again next time.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <div className="card flex items-center gap-6">
                <ScoreRing score={currentResult?.nervousness_score || 0} size={80} />
                <div>
                  <p className="text-mist text-xs uppercase tracking-widest font-mono mb-1">Nervousness</p>
                  <p className="text-chalk text-2xl font-mono font-semibold">
                    {currentResult?.nervousness_score} <span className="text-mist text-sm">/100</span>
                  </p>
                </div>
              </div>

              {currentResult?.content_feedback && (
                <div className="card bg-carbon border-azure/30">
                  <p className="text-azure text-xs uppercase tracking-widest font-mono mb-2">Answer Analysis</p>
                  <p className="text-chalk text-sm leading-relaxed">{currentResult.content_feedback}</p>
                </div>
              )}

              {currentResult?.better_answer && (
                <div className="card bg-carbon border-jade/30">
                  <p className="text-jade text-xs uppercase tracking-widest font-mono mb-2">Stronger Answer</p>
                  <p className="text-chalk/90 text-sm leading-relaxed italic">"{currentResult.better_answer}"</p>
                </div>
              )}
            </div>
          )}

          <button
            className="btn-primary w-full flex items-center justify-center gap-2 py-4 mt-6"
            onClick={handleNext}
          >
            {idx < questions.length - 1
              ? <><ChevronRight size={18} /> Next Question</>
              : <><CheckCircle size={18} /> See Final Score</>}
          </button>
        </div>
      </main>
    </>
  )

  // ── Done ────────────────────────────────────────────────────
  if (phase === 'done') {
    const scoreColor = avgScore < 35 ? 'text-jade' : avgScore < 60 ? 'text-amber' : 'text-ember'
    return (
      <>
        <NavBar onSignOut={onSignOut} userName={user?.email} />
        <main className="min-h-screen bg-obsidian px-4 py-8 flex items-center justify-center">
          <div className="max-w-md w-full text-center animate-slide-up">
            <p className="text-mist text-xs uppercase tracking-widest font-mono mb-2">Drill Complete!</p>
            <h2 className="heading-display text-5xl gradient-text mb-6">Nice Work</h2>

            <div className="card mb-6">
              <ScoreRing score={parseFloat(avgScore.toFixed(1))} size={100} />
              <p className={`text-3xl font-mono font-bold ${scoreColor} mt-4`}>
                {avgScore.toFixed(1)} <span className="text-mist text-base font-normal">/100 avg</span>
              </p>
              <p className="text-mist text-sm mt-2">
                {avgScore < 35 ? '🎉 Excellent delivery!' : avgScore < 60 ? '🟡 Getting better!' : '🔴 Keep practising!'}
              </p>
            </div>

            <div className="flex flex-col gap-3">
              <button className="btn-primary w-full flex items-center justify-center gap-2"
                onClick={() => { setPhase('intro'); setIdx(0); setResults([]); setQuestions(shuffle(DRILL_QUESTIONS).slice(0,5)) }}>
                <RotateCcw size={16} /> Drill Again
              </button>
              <button className="btn-secondary w-full" onClick={() => navigate('setup')}>
                Full Interview →
              </button>
              <button className="btn-ghost w-full" onClick={() => navigate('dashboard')}>
                ← Dashboard
              </button>
            </div>
          </div>
        </main>
        {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      </>
    )
  }

  return null
}