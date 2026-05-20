import React, { useEffect, useState, useRef } from 'react'
import { api } from '../lib/api'
import { NavBar, ScoreRing, Spinner, Toast } from '../components/UI'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer,
} from 'recharts'
import { Plus, ChevronRight, Activity } from 'lucide-react'

// ── Confetti ──────────────────────────────────────────────────
function Confetti({ active }) {
  const canvasRef = useRef(null)
  const animRef   = useRef(null)
  useEffect(() => {
    if (!active) return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
    const pieces = Array.from({ length: 120 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * -canvas.height,
      w: 8 + Math.random() * 8, h: 4 + Math.random() * 4,
      color: ['#FF4D1C','#FF8C42','#00E5A0','#4A9EFF','#8B5CF6'][Math.floor(Math.random()*5)],
      rot: Math.random() * 360, vx: (Math.random()-0.5)*3,
      vy: 2+Math.random()*4, vr: (Math.random()-0.5)*6,
    }))
    let frame = 0
    const draw = () => {
      ctx.clearRect(0,0,canvas.width,canvas.height)
      pieces.forEach(p => {
        p.x+=p.vx; p.y+=p.vy; p.rot+=p.vr
        ctx.save(); ctx.translate(p.x,p.y); ctx.rotate(p.rot*Math.PI/180)
        ctx.fillStyle=p.color; ctx.fillRect(-p.w/2,-p.h/2,p.w,p.h); ctx.restore()
      })
      frame++
      if (frame < 180) animRef.current = requestAnimationFrame(draw)
      else ctx.clearRect(0,0,canvas.width,canvas.height)
    }
    animRef.current = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(animRef.current)
  }, [active])
  if (!active) return null
  return <canvas ref={canvasRef} className="fixed inset-0 pointer-events-none z-50" style={{width:'100vw',height:'100vh'}} />
}

// ── Animated counter ──────────────────────────────────────────
function AnimatedNumber({ value, decimals = 0, duration = 1000 }) {
  const [display, setDisplay] = useState(0)
  const startRef = useRef(null)
  useEffect(() => {
    if (value === null || value === undefined) return
    const target = parseFloat(value) || 0
    startRef.current = null
    const animate = (ts) => {
      if (!startRef.current) startRef.current = ts
      const progress = Math.min((ts - startRef.current) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplay(eased * target)
      if (progress < 1) requestAnimationFrame(animate)
    }
    requestAnimationFrame(animate)
  }, [value, duration])
  return <span>{display.toFixed(decimals)}</span>
}

// ── Company logo ──────────────────────────────────────────────
function CompanyLogo({ company, size = 40 }) {
  const [failed, setFailed] = useState(false)
  const slug = company?.toLowerCase().replace(/[^a-z0-9]/g, '') || ''
  if (failed || !slug) {
    return (
      <div
        className="rounded-lg bg-steel flex items-center justify-center text-chalk font-display font-bold shrink-0"
        style={{ width: size, height: size, fontSize: size * 0.4 }}
      >
        {company?.[0]?.toUpperCase() || '?'}
      </div>
    )
  }
  return (
    <img
      src={`https://logo.clearbit.com/${slug}.com`}
      alt={company}
      className="rounded-lg object-contain bg-white shrink-0"
      style={{ width: size, height: size }}
      onError={() => setFailed(true)}
    />
  )
}

// ── Radar chart ───────────────────────────────────────────────
function PerformanceRadar({ sessions }) {
  const latest = sessions.find(s => s.overall_nervousness != null)
  if (!latest) return null
  const score = latest.overall_nervousness || 0
  const calm  = Math.max(0, 100 - score)
  const data = [
    { metric: 'Confidence',  value: Math.min(100, calm + 10) },
    { metric: 'Clarity',     value: Math.min(100, calm + 5)  },
    { metric: 'Pace',        value: Math.min(100, calm - 5)  },
    { metric: 'No Fillers',  value: Math.min(100, calm + 15) },
    { metric: 'Composure',   value: Math.min(100, calm)      },
  ]
  return (
    <div className="card animate-slide-up">
      <div className="flex items-center gap-2 mb-2">
        <Activity size={16} className="text-violet" />
        <span className="text-chalk font-medium text-sm">Performance Radar</span>
        <span className="text-mist text-xs ml-auto">{latest.company} · {latest.role}</span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <RadarChart data={data} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
          <PolarGrid stroke="#2A2A3C" />
          <PolarAngleAxis dataKey="metric" tick={{ fill: '#8B8BA0', fontSize: 11 }} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Radar
            name="Performance" dataKey="value"
            stroke="#8B5CF6" fill="#8B5CF6" fillOpacity={0.25} strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────
function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

function scoreColor(score) {
  if (score == null) return 'text-mist'
  return score < 35 ? 'text-jade' : score < 60 ? 'text-amber' : 'text-ember'
}

// ── Main Dashboard ────────────────────────────────────────────
export default function DashboardPage({ navigate, onSignOut, user }) {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading]   = useState(true)
  const [toast, setToast]       = useState(null)
  const [confetti, setConfetti] = useState(false)

  useEffect(() => {
    api.getDashboard()
      .then(d => {
        const s = d.sessions || []
        setSessions(s)
        if (s[0]?.status === 'completed' && s[0]?.overall_nervousness < 40) {
          setTimeout(() => setConfetti(true), 400)
          setTimeout(() => setConfetti(false), 4000)
        }
      })
      .catch(err => setToast({ message: err.message, type: 'error' }))
      .finally(() => setLoading(false))
  }, [])

  const completedCount = sessions.filter(s => s.status === 'completed').length
  const scoredSessions = sessions.filter(s => s.overall_nervousness != null)
  const avgScore = scoredSessions.length
    ? scoredSessions.reduce((a, b) => a + b.overall_nervousness, 0) / scoredSessions.length
    : null
  const bestScore = scoredSessions.reduce((best, s) =>
    best === null || s.overall_nervousness < best ? s.overall_nervousness : best, null)

  return (
    <>
      <Confetti active={confetti} />
      <NavBar onSignOut={onSignOut} userName={user?.email} />

      <main className="min-h-screen bg-obsidian px-4 py-8 md:px-8">
        <div className="max-w-4xl mx-auto">

          {/* Header */}
          <div className="flex items-end justify-between mb-8 animate-fade-in">
            <div>
              <p className="text-mist text-sm uppercase tracking-widest font-mono">Dashboard</p>
              <h1 className="heading-display text-5xl md:text-6xl mt-1">
                Ready to <span className="gradient-text">Unflinch?</span>
              </h1>
            </div>
            <button className="btn-primary flex items-center gap-2 shrink-0" onClick={() => navigate('setup')}>
              <Plus size={16} />
              <span className="hidden sm:inline">New Interview</span>
            </button>
          </div>

          {/* Animated stats */}
          {sessions.length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8 animate-slide-up">
              <div className="metric-card">
                <span className="text-mist text-xs uppercase tracking-widest">Sessions</span>
                <span className="text-chalk text-3xl font-mono font-semibold">
                  <AnimatedNumber value={sessions.length} />
                </span>
              </div>
              <div className="metric-card">
                <span className="text-mist text-xs uppercase tracking-widest">Completed</span>
                <span className="text-chalk text-3xl font-mono font-semibold">
                  <AnimatedNumber value={completedCount} />
                </span>
              </div>
              {avgScore != null && (
                <div className="metric-card">
                  <span className="text-mist text-xs uppercase tracking-widest">Avg Nervousness</span>
                  <span className={`text-3xl font-mono font-semibold ${scoreColor(avgScore)}`}>
                    <AnimatedNumber value={avgScore} decimals={1} />
                  </span>
                </div>
              )}
              {bestScore != null && (
                <div className="metric-card border-jade/30">
                  <span className="text-mist text-xs uppercase tracking-widest">Best Score</span>
                  <span className="text-jade text-3xl font-mono font-semibold">
                    <AnimatedNumber value={bestScore} decimals={1} />
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Radar chart */}
          {sessions.length >= 1 && scoredSessions.length > 0 && (
            <div className="mb-8">
              <PerformanceRadar sessions={sessions} />
            </div>
          )}

          {/* Session list */}
          <div>
            <h2 className="text-mist text-xs uppercase tracking-widest font-mono mb-4">Past Sessions</h2>

            {loading ? (
              <div className="flex justify-center py-16">
                <Spinner className="w-6 h-6 text-mist" />
              </div>
            ) : sessions.length === 0 ? (
              <div className="card text-center py-12">
                <p className="text-mist mb-4">No sessions yet. Start your first interview prep!</p>
                <button className="btn-primary" onClick={() => navigate('setup')}>
                  Start Interview →
                </button>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {sessions.map((s, i) => (
                  <div
                    key={s.id}
                    className="card cursor-pointer hover:border-ember/40 transition-all duration-200
                               flex items-center gap-4 animate-fade-in group"
                    style={{ animationDelay: `${i * 60}ms` }}
                    onClick={() => navigate('summary', { sessionId: s.id, readOnly: true })}
                  >
                    <CompanyLogo company={s.company} size={40} />

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-chalk font-semibold truncate">{s.role}</span>
                        <span className="text-mist text-xs">@</span>
                        <span className="text-chalk text-sm truncate">{s.company}</span>
                      </div>
                      <div className="flex items-center gap-3 mt-0.5 flex-wrap">
                        <span className="text-mist text-xs">{s.round}</span>
                        <span className="text-steel">·</span>
                        <span className="text-mist text-xs">{formatDate(s.created_at)}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-mono
                          ${s.status === 'completed' ? 'bg-jade/10 text-jade' : 'bg-amber/10 text-amber'}`}>
                          {s.status}
                        </span>
                      </div>
                    </div>

                    {s.overall_nervousness != null && (
                      <div className="text-right shrink-0">
                        <span className={`text-xl font-mono font-bold ${scoreColor(s.overall_nervousness)}`}>
                          {s.overall_nervousness}
                        </span>
                        <p className="text-mist text-xs">/100</p>
                      </div>
                    )}

                    <ChevronRight size={18} className="text-steel group-hover:text-chalk transition-colors shrink-0" />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </>
  )
}