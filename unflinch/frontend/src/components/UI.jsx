import React from 'react'
import { Loader2 } from 'lucide-react'

// ── Loading spinner ───────────────────────────────────────────
export function Spinner({ className = '' }) {
  return <Loader2 className={`animate-spin ${className}`} />
}

// ── Nervousness score ring ────────────────────────────────────
export function ScoreRing({ score = 0, size = 96 }) {
  const r      = 36
  const circ   = 2 * Math.PI * r
  const offset = circ - (score / 100) * circ

  const color =
    score < 35 ? '#00E5A0'  // jade – calm
    : score < 60 ? '#FF8C42' // amber – moderate
    : '#FF4D1C'              // ember – high

  return (
    <div className="score-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox="0 0 96 96">
        <circle cx="48" cy="48" r={r} fill="none" stroke="#2A2A3C" strokeWidth="6" />
        <circle
          cx="48" cy="48" r={r}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          transform="rotate(-90 48 48)"
          style={{ transition: 'stroke-dashoffset 0.8s ease' }}
        />
      </svg>
      <span
        className="absolute inset-0 flex items-center justify-center font-mono text-sm font-semibold"
        style={{ color }}
      >
        {Math.round(score)}
      </span>
    </div>
  )
}

// ── Metric pill ───────────────────────────────────────────────
export function MetricPill({ label, value, unit = '' }) {
  return (
    <div className="metric-card">
      <span className="text-mist text-xs uppercase tracking-widest">{label}</span>
      <span className="text-chalk text-xl font-mono font-medium">
        {value}<span className="text-mist text-sm ml-1">{unit}</span>
      </span>
    </div>
  )
}

// ── Toast notification ────────────────────────────────────────
export function Toast({ message, type = 'info', onClose }) {
  const bg =
    type === 'success' ? 'border-jade/50 bg-jade/10 text-jade'
    : type === 'error'  ? 'border-ember/50 bg-ember/10 text-ember'
    : 'border-azure/50 bg-azure/10 text-azure'

  return (
    <div
      className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50 border rounded-xl px-5 py-3 
                  text-sm font-body font-medium shadow-xl animate-slide-up flex items-center gap-3 ${bg}`}
    >
      {message}
      {onClose && (
        <button onClick={onClose} className="opacity-60 hover:opacity-100 ml-2">✕</button>
      )}
    </div>
  )
}

// ── Select input ──────────────────────────────────────────────
export function Select({ label, id, children, ...props }) {
  return (
    <div>
      {label && <label htmlFor={id} className="label">{label}</label>}
      <select id={id} className="input appearance-none cursor-pointer" {...props}>
        {children}
      </select>
    </div>
  )
}

// ── Toggle switch ─────────────────────────────────────────────
export function Toggle({ checked, onChange, label }) {
  return (
    <label className="flex items-center gap-3 cursor-pointer select-none">
      <div
        className={`relative w-11 h-6 rounded-full transition-colors duration-200
                    ${checked ? 'bg-ember' : 'bg-steel'}`}
        onClick={() => onChange(!checked)}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow
                      transition-transform duration-200 ${checked ? 'translate-x-5' : ''}`}
        />
      </div>
      {label && <span className="text-chalk text-sm font-medium">{label}</span>}
    </label>
  )
}

// ── Distraction popup ─────────────────────────────────────────
const DISTRACTION_QUESTIONS = [
  'Why was there a gap in your resume?',
  'What would your previous manager say is your biggest weakness?',
  'Have you ever been fired?',
  'Why did you leave your last job on such short notice?',
  'Describe a time you failed. What happened?',
  'Are you interviewing elsewhere? What makes you prefer us?',
]

export function DistractionModal({ onDismiss }) {
  const question = DISTRACTION_QUESTIONS[Math.floor(Math.random() * DISTRACTION_QUESTIONS.length)]
  const [elapsed, setElapsed] = React.useState(0)

  React.useEffect(() => {
    const t = setInterval(() => setElapsed(e => e + 1), 1000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="fixed inset-0 bg-obsidian/90 backdrop-blur-sm z-50 flex items-center justify-center p-6 animate-fade-in">
      <div className="card max-w-md w-full border-ember/40 bg-carbon">
        <div className="text-ember text-xs font-mono uppercase tracking-widest mb-4">
          ⚡ Distraction Mode
        </div>
        <p className="text-chalk text-lg font-body font-medium mb-2 leading-relaxed">
          {question}
        </p>
        <p className="text-mist text-sm mb-6">
          Take a breath. You have time. Click <strong className="text-chalk">Resume</strong> when ready.
        </p>
        <div className="flex items-center justify-between">
          <span className="font-mono text-mist text-sm">{elapsed}s elapsed</span>
          <button className="btn-primary" onClick={() => onDismiss(elapsed)}>
            Resume Recording →
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Page layout wrapper ───────────────────────────────────────
export function PageLayout({ children, className = '' }) {
  return (
    <main className={`min-h-screen bg-obsidian px-4 py-8 md:px-8 ${className}`}>
      <div className="max-w-3xl mx-auto">
        {children}
      </div>
    </main>
  )
}

// ── Nav bar ───────────────────────────────────────────────────
export function NavBar({ onSignOut, userName }) {
  return (
    <nav className="border-b border-steel bg-carbon/80 backdrop-blur-sm sticky top-0 z-40">
      <div className="max-w-5xl mx-auto px-4 md:px-8 h-14 flex items-center justify-between">
        <span className="heading-display text-2xl gradient-text">UNFLINCH</span>
        <div className="flex items-center gap-4">
          {userName && <span className="text-mist text-sm hidden sm:block">{userName}</span>}
          <button className="btn-ghost text-sm" onClick={onSignOut}>Sign out</button>
        </div>
      </div>
    </nav>
  )
}
