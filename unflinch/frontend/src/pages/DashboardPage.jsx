import React, { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { NavBar, ScoreRing, Spinner, Toast } from '../components/UI'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { Plus, ChevronRight, TrendingUp } from 'lucide-react'

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric'
  })
}

function NervousnessColor({ score }) {
  const color = score < 35 ? 'text-jade' : score < 60 ? 'text-amber' : 'text-ember'
  return <span className={`font-mono font-semibold ${color}`}>{score?.toFixed(1) ?? '—'}</span>
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-graphite border border-steel rounded-lg px-3 py-2 text-xs">
      <p className="text-mist mb-0.5">{label}</p>
      <p className="text-chalk font-mono font-semibold">{payload[0].value?.toFixed(1)} / 100</p>
    </div>
  )
}

export default function DashboardPage({ navigate, onSignOut, user }) {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading]   = useState(true)
  const [toast, setToast]       = useState(null)

  useEffect(() => {
    api.getDashboard()
      .then(d => setSessions(d.sessions || []))
      .catch(err => setToast({ message: err.message, type: 'error' }))
      .finally(() => setLoading(false))
  }, [])

  const chartData = [...sessions]
    .filter(s => s.overall_nervousness != null)
    .reverse()
    .map(s => ({
      date: new Date(s.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }),
      score: s.overall_nervousness,
    }))

  const completedCount = sessions.filter(s => s.status === 'completed').length
  const avgScore = sessions.length
    ? (sessions.filter(s => s.overall_nervousness).reduce((a, b) => a + (b.overall_nervousness || 0), 0) /
       Math.max(sessions.filter(s => s.overall_nervousness).length, 1)).toFixed(1)
    : null

  return (
    <>
      <NavBar onSignOut={onSignOut} userName={user?.phone} />
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
            <button
              className="btn-primary flex items-center gap-2 shrink-0"
              onClick={() => navigate('setup')}
            >
              <Plus size={16} />
              <span className="hidden sm:inline">New Interview</span>
            </button>
          </div>

          {/* Stats row */}
          {sessions.length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8 animate-slide-up">
              <div className="metric-card">
                <span className="text-mist text-xs uppercase tracking-widest">Sessions</span>
                <span className="text-chalk text-3xl font-mono font-semibold">{sessions.length}</span>
              </div>
              <div className="metric-card">
                <span className="text-mist text-xs uppercase tracking-widest">Completed</span>
                <span className="text-chalk text-3xl font-mono font-semibold">{completedCount}</span>
              </div>
              {avgScore && (
                <div className="metric-card col-span-2 md:col-span-1">
                  <span className="text-mist text-xs uppercase tracking-widest">Avg Nervousness</span>
                  <NervousnessColor score={parseFloat(avgScore)} />
                </div>
              )}
            </div>
          )}

          {/* Progress chart */}
          {chartData.length >= 2 && (
            <div className="card mb-8 animate-slide-up">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp size={16} className="text-jade" />
                <span className="text-chalk font-medium text-sm">Nervousness Over Time</span>
              </div>
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={chartData}>
                  <XAxis dataKey="date" tick={{ fill: '#8B8BA0', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fill: '#8B8BA0', fontSize: 11 }} axisLine={false} tickLine={false} width={30} />
                  <Tooltip content={<CustomTooltip />} />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="#FF4D1C"
                    strokeWidth={2}
                    dot={{ r: 3, fill: '#FF4D1C', strokeWidth: 0 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
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
                    <ScoreRing score={s.overall_nervousness ?? 0} size={56} />

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-chalk font-semibold truncate">{s.role}</span>
                        <span className="text-mist text-xs">at</span>
                        <span className="text-chalk text-sm truncate">{s.company}</span>
                      </div>
                      <div className="flex items-center gap-3 mt-0.5">
                        <span className="text-mist text-xs">{s.round} round</span>
                        <span className="text-steel">·</span>
                        <span className="text-mist text-xs">{formatDate(s.created_at)}</span>
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-mono
                            ${s.status === 'completed'
                              ? 'bg-jade/10 text-jade'
                              : 'bg-amber/10 text-amber'}`}
                        >
                          {s.status}
                        </span>
                      </div>
                    </div>

                    <ChevronRight
                      size={18}
                      className="text-steel group-hover:text-chalk transition-colors shrink-0"
                    />
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
