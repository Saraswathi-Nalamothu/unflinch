import React, { useEffect, useState, useRef } from 'react'
import { api } from '../lib/api'
import { useRecorder } from '../hooks/useRecorder'
import { NavBar, ScoreRing, MetricPill, DistractionModal, Spinner, Toast } from '../components/UI'
import { Mic, MicOff, ChevronRight, CheckCircle, LogOut, AlertTriangle, RotateCcw, Lightbulb, Star, Volume2 } from 'lucide-react'

function ProgressBar({ current, total }) {
  return (
    <div className="flex gap-1.5 mb-2">
      {Array.from({ length: total }).map((_, i) => (
        <div key={i} className={`h-1 flex-1 rounded-full transition-all duration-500
          ${i < current ? 'bg-ember' : i === current ? 'bg-ember/40' : 'bg-steel'}`} />
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
            ${recording ? 'bg-ember hover:bg-red-600' : 'bg-graphite border-2 border-steel hover:border-ember hover:bg-steel'}`}
        >
          {recording ? <MicOff size={28} className="text-white" /> : <Mic size={28} className="text-chalk" />}
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
      {!recording && <p className="text-mist text-sm">Click to record your answer</p>}
    </div>
  )
}

function ExitModal({ onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 bg-obsidian/90 backdrop-blur-sm z-50 flex items-center justify-center p-6 animate-fade-in">
      <div className="card max-w-sm w-full border-ember/40 bg-carbon">
        <div className="flex items-center gap-2 text-ember mb-4">
          <LogOut size={18} />
          <span className="font-semibold">Exit Interview?</span>
        </div>
        <p className="text-chalk text-sm mb-2">Are you sure you want to quit this session?</p>
        <p className="text-mist text-xs mb-6">Your progress so far will be saved.</p>
        <div className="flex gap-3">
          <button className="btn-secondary flex-1" onClick={onCancel}>Keep Going</button>
          <button className="btn-primary flex-1 bg-steel hover:bg-graphite" onClick={onConfirm}>Exit Session</button>
        </div>
      </div>
    </div>
  )
}

// No speech warning card
function NoSpeechCard({ onRetry, onSkip }) {
  return (
    <div className="animate-slide-up flex flex-col gap-4">
      <div className="card border-amber/50 bg-amber/5">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 bg-amber/20 rounded-xl flex items-center justify-center shrink-0">
            <AlertTriangle size={20} className="text-amber" />
          </div>
          <div>
            <p className="text-amber font-semibold mb-1">No speech detected! 🎙️</p>
            <p className="text-chalk/80 text-sm leading-relaxed mb-2">
              We couldn't hear anything. Please:
            </p>
            <ul className="text-mist text-sm space-y-1">
              <li>• Make sure your microphone is connected</li>
              <li>• Speak loudly and clearly into the mic</li>
              <li>• Check browser mic permissions</li>
              <li>• Move closer to the microphone</li>
            </ul>
          </div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <button className="btn-secondary flex items-center justify-center gap-2" onClick={onRetry}>
          <RotateCcw size={16} /> Try Again
        </button>
        <button className="btn-primary flex items-center justify-center gap-2" onClick={onSkip}>
          Skip Question <ChevronRight size={16} />
        </button>
      </div>
    </div>
  )
}

// Rich feedback card
function FeedbackCard({ result, isLast, onNext, onExit }) {
  const [showBetter, setShowBetter] = useState(false)

  return (
    <div className="animate-slide-up flex flex-col gap-4">
      {/* Score */}
      <div className="card flex items-center gap-6">
        <ScoreRing score={result.nervousness_score} size={80} />
        <div>
          <p className="text-mist text-xs uppercase tracking-widest font-mono mb-1">Nervousness Score</p>
          <p className="text-chalk text-2xl font-mono font-semibold">
            {result.nervousness_score} <span className="text-mist text-sm font-normal">/100</span>
          </p>
          <p className="text-mist text-xs mt-1">
            {result.nervousness_score < 35 ? '🟢 Calm & confident'
             : result.nervousness_score < 60 ? '🟡 Some nerves detected'
             : '🔴 High nervousness — keep practising!'}
          </p>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-3 gap-3">
        <MetricPill label="Fillers" value={result.filler_count} />
        <MetricPill label="Pauses" value={result.pause_count} />
        <MetricPill label="Speech Rate" value={result.speech_rate} unit="w/s" />
      </div>

      {/* Content feedback */}
      {result.content_feedback && (
        <div className="card bg-carbon border-azure/30">
          <div className="flex items-center gap-2 mb-2">
            <Lightbulb size={14} className="text-azure" />
            <p className="text-azure text-xs uppercase tracking-widest font-mono">Answer Analysis</p>
          </div>
          <p className="text-chalk text-sm leading-relaxed">{result.content_feedback}</p>
        </div>
      )}

      {/* Voice tip */}
      {result.voice_feedback && (
        <div className="card bg-carbon border-violet/30">
          <div className="flex items-center gap-2 mb-2">
            <Volume2 size={14} className="text-violet" />
            <p className="text-violet text-xs uppercase tracking-widest font-mono">Voice & Delivery</p>
          </div>
          <p className="text-chalk text-sm leading-relaxed">{result.voice_feedback}</p>
        </div>
      )}

      {/* Better answer */}
      {result.better_answer && (
        <div className="card bg-carbon border-jade/30">
          <button className="w-full flex items-center justify-between" onClick={() => setShowBetter(v => !v)}>
            <div className="flex items-center gap-2">
              <Star size={14} className="text-jade" />
              <p className="text-jade text-xs uppercase tracking-widest font-mono">Stronger Answer</p>
            </div>
            <span className="text-mist text-xs">{showBetter ? '▲ Hide' : '▼ Show'}</span>
          </button>
          {showBetter && (
            <div className="mt-3 pt-3 border-t border-steel">
              <p className="text-chalk/90 text-sm leading-relaxed italic">"{result.better_answer}"</p>
              <p className="text-mist text-xs mt-2">💡 Adapt this with your own experience.</p>
            </div>
          )}
        </div>
      )}

      {/* Transcript */}
      <details className="card cursor-pointer">
        <summary className="text-mist text-xs uppercase tracking-widest font-mono select-none">Your Transcript ▸</summary>
        <p className="text-chalk/80 text-sm leading-relaxed mt-3">{result.transcript || '(no speech detected)'}</p>
      </details>

      {/* Next */}
      <button className="btn-primary w-full flex items-center justify-center gap-2 py-4 text-base" onClick={onNext}>
        {isLast ? <><CheckCircle size={18} /> Finish & View Summary</> : <>Next Question <ChevronRight size={18} /></>}
      </button>
      <button className="text-mist text-xs text-center hover:text-ember transition-colors" onClick={onExit}>
        Exit session early
      </button>
    </div>
  )
}

export default function InterviewPage({ navigate, onSignOut, user, params }) {
  const { sessionId, distractionEnabled } = params || {}

  const [questions, setQuestions]         = useState([])
  const [currentIdx, setCurrentIdx]       = useState(0)
  const [analysing, setAnalysing]         = useState(false)
  const [showDistraction, setDistraction] = useState(false)
  const [distractionUsed, setUsed]        = useState(false)
  const [result, setResult]               = useState(null)
  const [noSpeech, setNoSpeech]           = useState(false)
  const [loading, setLoading]             = useState(true)
  const [showExitModal, setShowExitModal] = useState(false)
  const [toast, setToast]                 = useState(null)

  const { recording, audioBlob, duration, error, start, stop, reset } = useRecorder(120)
  const distractionTimerRef = useRef(null)

  useEffect(() => {
    if (!sessionId) return navigate('dashboard')
    api.getSession(sessionId)
      .then(d => setQuestions(d.questions || []))
      .catch(err => setToast({ message: err.message, type: 'error' }))
      .finally(() => setLoading(false))
  }, [sessionId])

  useEffect(() => {
    if (error) setToast({ message: error, type: 'error' })
  }, [error])

  function handleStartRecording() {
    setNoSpeech(false)
    reset()
    start()
    if (distractionEnabled && !distractionUsed && currentIdx > 0 && Math.random() < 0.5) {
      const delay = 5000 + Math.random() * 10000
      distractionTimerRef.current = setTimeout(() => { stop(); setDistraction(true) }, delay)
    }
  }

  function handleStopRecording() {
    clearTimeout(distractionTimerRef.current)
    stop()
  }

  function handleDistractionDismiss(recoveryTime) {
    setDistraction(false)
    setUsed(true)
    submitAnswer(recoveryTime)
  }

  async function submitAnswer(recoveryTime = null) {
    if (!audioBlob && !recoveryTime) return
    const question = questions[currentIdx]
    if (!question) return

    const fd = new FormData()
    fd.append('session_id', sessionId)
    fd.append('question_id', question.id)
    fd.append('question_text', question.question_text)
    if (recoveryTime !== null) fd.append('recovery_time', String(recoveryTime))
    if (audioBlob) fd.append('audio', audioBlob, 'answer.webm')

    setAnalysing(true)
    setResult(null)
    setNoSpeech(false)

    try {
      const res = await api.analyzeAnswer(fd)

      // Backend returns no_speech:true if silent or too short
      if (res.no_speech) {
        setNoSpeech(true)
        return
      }

      setResult(res)
    } catch (err) {
      setToast({ message: 'Analysis failed: ' + err.message, type: 'error' })
    } finally {
      setAnalysing(false)
    }
  }

  useEffect(() => {
    if (audioBlob && !analysing && !showDistraction) submitAnswer()
  }, [audioBlob])

  function handleNext() {
    if (currentIdx < questions.length - 1) {
      setCurrentIdx(i => i + 1)
      setResult(null)
      setNoSpeech(false)
      reset()
    } else {
      api.saveSession(sessionId).catch(() => {})
      navigate('summary', { sessionId })
    }
  }

  function handleExitConfirm() {
    api.saveSession(sessionId).catch(() => {})
    navigate('dashboard')
  }

  if (loading) return (
    <div className="min-h-screen bg-obsidian flex items-center justify-center">
      <Spinner className="w-8 h-8 text-mist" />
    </div>
  )

  const question = questions[currentIdx]
  const isLast   = currentIdx === questions.length - 1

  return (
    <>
      <NavBar onSignOut={onSignOut} userName={user?.email} />
      {showDistraction && <DistractionModal onDismiss={handleDistractionDismiss} />}
      {showExitModal && <ExitModal onConfirm={handleExitConfirm} onCancel={() => setShowExitModal(false)} />}

      <main className="min-h-screen bg-obsidian px-4 py-8 md:px-8">
        <div className="max-w-2xl mx-auto">

          {/* Progress + exit */}
          <div className="flex items-center gap-3 mb-2">
            <div className="flex-1"><ProgressBar current={currentIdx} total={questions.length} /></div>
            <button
              className="shrink-0 flex items-center gap-1.5 text-mist text-xs hover:text-ember
                transition-colors border border-steel hover:border-ember/40 rounded-lg px-3 py-1.5 mb-2"
              onClick={() => setShowExitModal(true)}
            >
              <LogOut size={13} /> Exit
            </button>
          </div>

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

          {/* Question */}
          <div className="card mb-6 border-steel/80 animate-slide-up" key={currentIdx}>
            <p className="text-mist text-xs uppercase tracking-widest mb-3 font-mono">Your question</p>
            <p className="text-chalk text-xl md:text-2xl leading-relaxed font-body">
              {question?.question_text}
            </p>
          </div>

          {/* Recording */}
          {!result && !analysing && !noSpeech && (
            <div className="flex flex-col items-center py-8 gap-6 animate-fade-in">
              <RecordButton
                recording={recording}
                onStart={handleStartRecording}
                onStop={handleStopRecording}
                duration={duration}
              />
              {recording && (
                <p className="text-mist text-xs text-center max-w-xs">
                  Speak clearly and loudly. Click the mic again to stop.
                </p>
              )}
              {!recording && (
                <button className="text-mist text-xs hover:text-chalk underline underline-offset-2" onClick={handleNext}>
                  Skip this question →
                </button>
              )}
            </div>
          )}

          {/* Analysing */}
          {analysing && (
            <div className="flex flex-col items-center py-12 gap-4 animate-fade-in">
              <Spinner className="w-8 h-8 text-ember" />
              <p className="text-mist text-sm">Analysing your answer…</p>
              <p className="text-mist/50 text-xs">Transcribing + AI feedback</p>
            </div>
          )}

          {/* No speech */}
          {noSpeech && !analysing && (
            <NoSpeechCard
              onRetry={() => { setNoSpeech(false); reset() }}
              onSkip={handleNext}
            />
          )}

          {/* Results */}
          {result && !analysing && !noSpeech && (
            <FeedbackCard
              result={result}
              isLast={isLast}
              onNext={handleNext}
              onExit={() => setShowExitModal(true)}
            />
          )}
        </div>
      </main>

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </>
  )
}