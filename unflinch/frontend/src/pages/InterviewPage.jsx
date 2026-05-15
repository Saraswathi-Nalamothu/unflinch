import React, { useEffect, useState, useRef } from 'react'
import { api } from '../lib/api'
import { useRecorder } from '../hooks/useRecorder'
import { NavBar, ScoreRing, MetricPill, DistractionModal, Spinner, Toast } from '../components/UI'
import { Mic, MicOff, ChevronRight, CheckCircle } from 'lucide-react'

function ProgressBar({ current, total }) {
  return (
    <div className="flex gap-1.5 mb-6">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`h-1 flex-1 rounded-full transition-all duration-500
            ${i < current ? 'bg-ember' : i === current ? 'bg-ember/40' : 'bg-steel'}`}
        />
      ))}
    </div>
  )
}

function RecordButton({ recording, onStart, onStop, duration }) {
  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative">
        {recording && (
          <>
            <div className="absolute inset-0 rounded-full bg-ember/30 sonar-ring" />
            <div className="absolute inset-0 rounded-full bg-ember/20 sonar-ring-2" />
          </>
        )}
        <button
          onClick={recording ? onStop : onStart}
          className={`relative w-20 h-20 rounded-full flex items-center justify-center
                      transition-all duration-200 active:scale-95 shadow-lg
                      ${recording
                        ? 'bg-ember hover:bg-red-600'
                        : 'bg-graphite border-2 border-steel hover:border-ember hover:bg-steel'}`}
        >
          {recording
            ? <MicOff size={28} className="text-white" />
            : <Mic size={28} className="text-chalk" />}
        </button>
      </div>
      {recording && (
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 bg-ember rounded-full animate-pulse-slow" />
          <span className="font-mono text-sm text-mist">
            {Math.floor(duration / 60)}:{String(duration % 60).padStart(2, '0')} / 2:00
          </span>
        </div>
      )}
      {!recording && (
        <p className="text-mist text-sm">{recording ? '' : 'Click to record your answer'}</p>
      )}
    </div>
  )
}

export default function InterviewPage({ navigate, onSignOut, user, params }) {
  const { sessionId, distractionEnabled } = params || {}

  const [questions, setQuestions]         = useState([])
  const [currentIdx, setCurrentIdx]       = useState(0)
  const [answers, setAnswers]             = useState([])   // analysed results per question
  const [analysing, setAnalysing]         = useState(false)
  const [showDistraction, setDistraction] = useState(false)
  const [distractionUsed, setUsed]        = useState(false)
  const [result, setResult]               = useState(null)  // latest analysis result
  const [loading, setLoading]             = useState(true)
  const [toast, setToast]                 = useState(null)

  const { recording, audioBlob, duration, error, start, stop, reset } = useRecorder(120)

  // ── Load questions ────────────────────────────────────────
  useEffect(() => {
    if (!sessionId) return navigate('dashboard')
    api.getSession(sessionId)
      .then(d => setQuestions(d.questions || []))
      .catch(err => setToast({ message: err.message, type: 'error' }))
      .finally(() => setLoading(false))
  }, [sessionId])

  // ── Recorder error ───────────────────────────────────────
  useEffect(() => {
    if (error) setToast({ message: error, type: 'error' })
  }, [error])

  // ── Distraction trigger ──────────────────────────────────
  const distractionTimerRef = useRef(null)

  function handleStartRecording() {
    reset()
    start()

    // Trigger distraction on a random question (not first, not if already used)
    if (distractionEnabled && !distractionUsed && currentIdx > 0 && Math.random() < 0.5) {
      const delay = 5000 + Math.random() * 10000 // 5–15s into recording
      distractionTimerRef.current = setTimeout(() => {
        stop()
        setDistraction(true)
      }, delay)
    }
  }

  function handleStopRecording() {
    clearTimeout(distractionTimerRef.current)
    stop()
  }

  function handleDistractionDismiss(recoveryTime) {
    setDistraction(false)
    setUsed(true)
    // Immediately submit what we have with recovery_time penalty
    submitAnswer(recoveryTime)
  }

  // ── Submit answer blob ───────────────────────────────────
  async function submitAnswer(recoveryTime = null) {
    if (!audioBlob && !recoveryTime) return

    const question = questions[currentIdx]
    if (!question) return

    const fd = new FormData()
    fd.append('session_id', sessionId)
    fd.append('question_id', question.id)
    if (recoveryTime !== null) fd.append('recovery_time', String(recoveryTime))
    if (audioBlob) fd.append('audio', audioBlob, 'answer.webm')

    setAnalysing(true)
    setResult(null)
    try {
      const res = await api.analyzeAnswer(fd)
      setResult(res)
      setAnswers(prev => [...prev, { ...res, questionId: question.id }])
    } catch (err) {
      setToast({ message: 'Analysis failed: ' + err.message, type: 'error' })
    } finally {
      setAnalysing(false)
    }
  }

  // Auto-submit when blob ready (after stop)
  useEffect(() => {
    if (audioBlob && !analysing && !showDistraction) {
      submitAnswer()
    }
  }, [audioBlob])

  function handleNext() {
    if (currentIdx < questions.length - 1) {
      setCurrentIdx(i => i + 1)
      setResult(null)
      reset()
    } else {
      // All done → go to summary
      api.saveSession(sessionId).catch(() => {})
      navigate('summary', { sessionId })
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-obsidian flex items-center justify-center">
        <Spinner className="w-8 h-8 text-mist" />
      </div>
    )
  }

  const question = questions[currentIdx]
  const isLast   = currentIdx === questions.length - 1

  return (
    <>
      <NavBar onSignOut={onSignOut} userName={user?.phone} />

      {showDistraction && (
        <DistractionModal onDismiss={handleDistractionDismiss} />
      )}

      <main className="min-h-screen bg-obsidian px-4 py-8 md:px-8">
        <div className="max-w-2xl mx-auto">

          {/* Progress */}
          <ProgressBar current={currentIdx} total={questions.length} />

          {/* Question counter */}
          <div className="flex items-center justify-between mb-4">
            <span className="text-mist text-xs font-mono uppercase tracking-widest">
              Question {currentIdx + 1} of {questions.length}
            </span>
            {distractionEnabled && (
              <span className="text-amber text-xs font-mono border border-amber/30 rounded-full px-3 py-1">
                ⚡ Distraction On
              </span>
            )}
          </div>

          {/* Question card */}
          <div className="card mb-6 border-steel/80 animate-slide-up" key={currentIdx}>
            <p className="text-mist text-xs uppercase tracking-widest mb-3 font-mono">
              Your question
            </p>
            <p className="text-chalk text-xl md:text-2xl leading-relaxed font-body">
              {question?.question_text}
            </p>
          </div>

          {/* Recording section */}
          {!result && !analysing && (
            <div className="flex flex-col items-center py-8 gap-6 animate-fade-in">
              <RecordButton
                recording={recording}
                onStart={handleStartRecording}
                onStop={handleStopRecording}
                duration={duration}
              />
              {recording && (
                <p className="text-mist text-xs text-center max-w-xs">
                  Speak clearly and naturally. Click the mic again to stop recording.
                </p>
              )}
            </div>
          )}

          {/* Analysing state */}
          {analysing && (
            <div className="flex flex-col items-center py-12 gap-4 animate-fade-in">
              <Spinner className="w-8 h-8 text-ember" />
              <p className="text-mist text-sm">Analysing your answer…</p>
            </div>
          )}

          {/* Results */}
          {result && !analysing && (
            <div className="animate-slide-up flex flex-col gap-4">
              {/* Score row */}
              <div className="card flex items-center gap-6">
                <ScoreRing score={result.nervousness_score} size={80} />
                <div>
                  <p className="text-mist text-xs uppercase tracking-widest font-mono mb-1">Nervousness Score</p>
                  <p className="text-chalk text-2xl font-mono font-semibold">
                    {result.nervousness_score} <span className="text-mist text-sm font-normal">/ 100</span>
                  </p>
                </div>
              </div>

              {/* Metrics grid */}
              <div className="grid grid-cols-3 gap-3">
                <MetricPill label="Fillers" value={result.filler_count} />
                <MetricPill label="Pauses" value={result.pause_count} />
                <MetricPill label="Speech Rate" value={result.speech_rate} unit="w/s" />
              </div>

              {/* Tip */}
              <div className="card bg-carbon border-azure/30">
                <p className="text-azure text-xs uppercase tracking-widest font-mono mb-2">Improvement Tip</p>
                <p className="text-chalk text-sm leading-relaxed">{result.improvement_tip}</p>
              </div>

              {/* Transcript */}
              <details className="card cursor-pointer">
                <summary className="text-mist text-xs uppercase tracking-widest font-mono select-none">
                  Transcript ▸
                </summary>
                <p className="text-chalk/80 text-sm leading-relaxed mt-3 font-body">
                  {result.transcript || '(no speech detected)'}
                </p>
              </details>

              {/* Next button */}
              <button
                className="btn-primary w-full flex items-center justify-center gap-2 py-4 text-base"
                onClick={handleNext}
              >
                {isLast ? (
                  <><CheckCircle size={18} /> Finish & View Summary</>
                ) : (
                  <>Next Question <ChevronRight size={18} /></>
                )}
              </button>
            </div>
          )}
        </div>
      </main>

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </>
  )
}
