import React, { useEffect, useState } from 'react'
import { NavBar, Spinner, Toast } from '../components/UI'
import { supabase } from '../lib/supabase'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { TrendingDown, AlertTriangle, CheckCircle, BarChart2 } from 'lucide-react'

const FILLER_WORDS = ['um','uh','like','so','actually','basically','you know','right','well','kinda','kind of']

function countFillerBreakdown(transcripts) {
  const counts = {}
  FILLER_WORDS.forEach(f => { counts[f] = 0 })
  transcripts.forEach(text => {
    if (!text) return
    const lower = text.toLowerCase()
    FILLER_WORDS.forEach(filler => {
      const pattern = new RegExp(`\\b${filler.replace(' ', '\\s+')}\\b`, 'gi')
      const matches = lower.match(pattern)
      if (matches) counts[filler] += matches.length
    })
  })
  return Object.entries(counts)
    .map(([word, count]) => ({ word, count }))
    .filter(x => x.count > 0)
    .sort((a, b) => b.count - a.count)
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-graphite border border-steel rounded-lg px-3 py-2 text-xs">
      <p className="text-chalk font-mono">{payload[0].payload.word}: <span className="text-ember font-bold">{payload[0].value}</span></p>
    </div>
  )
}

export default function WeaknessPage({ navigate, onSignOut, user }) {
  const [loading, setLoading]       = useState(true)
  const [answers, setAnswers]       = useState([])
  const [sessions, setSessions]     = useState([])
  const [fillerData, setFillerData] = useState([])
  const [toast, setToast]           = useState(null)

  useEffect(() => {
    async function load() {
      try {
        const { data: { session } } = await supabase.auth.getSession()
        const userId = session?.user?.id
        if (!userId) return

        // Get all sessions for user
        const { data: sess } = await supabase
          .from('sessions')
          .select('id,company,role,overall_nervousness,created_at,status')
          .eq('user_id', userId)
          .order('created_at', { ascending: false })

        setSessions(sess || [])

        if (!sess?.length) { setLoading(false); return }

        // Get all answers
        const sessionIds = sess.map(s => s.id)
        const { data: ans } = await supabase
          .from('answers')
          .select('transcript,filler_count,pause_count,speech_rate,nervousness_score,improvement_tip,session_id')
          .in('session_id', sessionIds)

        setAnswers(ans || [])

        // Filler breakdown
        const transcripts = (ans || []).map(a => a.transcript).filter(Boolean)
        setFillerData(countFillerBreakdown(transcripts))
      } catch (err) {
        setToast({ message: err.message, type: 'error' })
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  // Stats
  const totalAnswers   = answers.length
  const avgFillers     = totalAnswers ? (answers.reduce((a,b) => a + (b.filler_count||0), 0) / totalAnswers).toFixed(1) : 0
  const avgPauses      = totalAnswers ? (answers.reduce((a,b) => a + (b.pause_count||0), 0) / totalAnswers).toFixed(1) : 0
  const avgRate        = totalAnswers ? (answers.reduce((a,b) => a + (b.speech_rate||0), 0) / totalAnswers).toFixed(1) : 0
  const avgNervousness = totalAnswers ? (answers.reduce((a,b) => a + (b.nervousness_score||0), 0) / totalAnswers).toFixed(1) : 0

  // Most common tip
  const tipCounts = {}
  answers.forEach(a => {
    if (!a.improvement_tip) return
    const key = a.improvement_tip.slice(0, 60)
    tipCounts[key] = (tipCounts[key] || 0) + 1
  })
  const topTips = Object.entries(tipCounts).sort((a,b) => b[1]-a[1]).slice(0, 3)

  // Worst questions (highest nervousness)
  const worstAnswers = [...answers]
    .filter(a => a.nervousness_score != null)
    .sort((a,b) => b.nervousness_score - a.nervousness_score)
    .slice(0, 3)

  // Progress: nervousness over last 5 sessions
  const trend = sessions
    .filter(s => s.overall_nervousness != null)
    .slice(0, 5)
    .reverse()

  const improving = trend.length >= 2 && trend[trend.length-1].overall_nervousness < trend[0].overall_nervousness

  if (loading) return (
    <div className="min-h-screen bg-obsidian flex items-center justify-center">
      <Spinner className="w-8 h-8 text-mist" />
    </div>
  )

  return (
    <>
      <NavBar onSignOut={onSignOut} userName={user?.email} />
      <main className="min-h-screen bg-obsidian px-4 py-8 md:px-8">
        <div className="max-w-3xl mx-auto">

          {/* Header */}
          <div className="mb-8 animate-fade-in">
            <p className="text-mist text-xs uppercase tracking-widest font-mono mb-1">Analytics</p>
            <h1 className="heading-display text-5xl">
              <span className="gradient-text">Weakness</span> Tracker
            </h1>
            <p className="text-mist text-sm mt-2">
              Based on {totalAnswers} answer{totalAnswers !== 1 ? 's' : ''} across {sessions.length} session{sessions.length !== 1 ? 's' : ''}
            </p>
          </div>

          {totalAnswers === 0 ? (
            <div className="card text-center py-16">
              <BarChart2 size={32} className="text-mist mx-auto mb-4" />
              <p className="text-mist mb-4">No data yet. Complete an interview session first!</p>
              <button className="btn-primary" onClick={() => navigate('setup')}>Start Interview →</button>
            </div>
          ) : (
            <>
              {/* Trend banner */}
              {trend.length >= 2 && (
                <div className={`card mb-6 flex items-center gap-3 border-${improving ? 'jade' : 'ember'}/30 animate-fade-in`}>
                  {improving
                    ? <CheckCircle size={20} className="text-jade shrink-0" />
                    : <AlertTriangle size={20} className="text-amber shrink-0" />}
                  <div>
                    <p className="text-chalk font-medium text-sm">
                      {improving ? 'You\'re improving! 🎉' : 'Keep practising — you\'ll get there!'}
                    </p>
                    <p className="text-mist text-xs">
                      Nervousness: {trend[0].overall_nervousness} → {trend[trend.length-1].overall_nervousness}
                      {improving ? ' ↓ getting calmer' : ' ↑ keep going'}
                    </p>
                  </div>
                </div>
              )}

              {/* Overall stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 animate-slide-up">
                {[
                  { label: 'Avg Nervousness', value: avgNervousness, unit: '/100',
                    color: avgNervousness < 35 ? 'text-jade' : avgNervousness < 60 ? 'text-amber' : 'text-ember' },
                  { label: 'Avg Fillers', value: avgFillers, unit: '/ans', color: 'text-chalk' },
                  { label: 'Avg Pauses', value: avgPauses, unit: '/ans', color: 'text-chalk' },
                  { label: 'Avg Speech Rate', value: avgRate, unit: 'w/s', color: 'text-chalk' },
                ].map(s => (
                  <div key={s.label} className="metric-card">
                    <span className="text-mist text-xs uppercase tracking-widest">{s.label}</span>
                    <span className={`text-2xl font-mono font-semibold ${s.color}`}>
                      {s.value}<span className="text-mist text-xs ml-1">{s.unit}</span>
                    </span>
                  </div>
                ))}
              </div>

              {/* Filler word breakdown chart */}
              {fillerData.length > 0 && (
                <div className="card mb-6 animate-slide-up">
                  <div className="flex items-center gap-2 mb-4">
                    <TrendingDown size={16} className="text-ember" />
                    <p className="text-chalk font-medium text-sm">Filler Word Breakdown</p>
                    <span className="text-mist text-xs ml-auto">
                      Total: {fillerData.reduce((a,b) => a+b.count,0)} fillers
                    </span>
                  </div>
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={fillerData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                      <XAxis dataKey="word" tick={{ fill: '#8B8BA0', fontSize: 11 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: '#8B8BA0', fontSize: 11 }} axisLine={false} tickLine={false} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="count" radius={[4,4,0,0]}>
                        {fillerData.map((entry, i) => (
                          <Cell key={i} fill={i === 0 ? '#FF4D1C' : i === 1 ? '#FF8C42' : '#2A2A3C'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  {fillerData[0] && (
                    <p className="text-mist text-xs mt-2 text-center">
                      Your most used filler: <span className="text-ember font-mono font-semibold">"{fillerData[0].word}"</span> ({fillerData[0].count} times)
                    </p>
                  )}
                </div>
              )}

              {/* Most recurring tips */}
              {topTips.length > 0 && (
                <div className="card mb-6 animate-slide-up">
                  <div className="flex items-center gap-2 mb-4">
                    <AlertTriangle size={16} className="text-amber" />
                    <p className="text-chalk font-medium text-sm">Recurring Weaknesses</p>
                  </div>
                  <div className="flex flex-col gap-3">
                    {topTips.map(([tip, count], i) => (
                      <div key={i} className="flex items-start gap-3">
                        <span className={`text-xs font-mono font-bold px-2 py-1 rounded-lg shrink-0
                          ${i===0 ? 'bg-ember/20 text-ember' : i===1 ? 'bg-amber/20 text-amber' : 'bg-steel text-mist'}`}>
                          #{i+1}
                        </span>
                        <div className="flex-1">
                          <p className="text-chalk text-sm leading-relaxed">{tip}…</p>
                          <p className="text-mist text-xs mt-0.5">Flagged {count} time{count!==1?'s':''}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Hardest questions */}
              {worstAnswers.length > 0 && (
                <div className="card mb-8 animate-slide-up">
                  <div className="flex items-center gap-2 mb-4">
                    <AlertTriangle size={16} className="text-ember" />
                    <p className="text-chalk font-medium text-sm">Hardest Answers</p>
                    <span className="text-mist text-xs ml-auto">Highest nervousness</span>
                  </div>
                  <div className="flex flex-col gap-3">
                    {worstAnswers.map((ans, i) => {
                      const sess = sessions.find(s => s.id === ans.session_id)
                      return (
                        <div key={i} className="flex items-start gap-3 border-b border-steel/40 pb-3 last:border-0 last:pb-0">
                          <span className="text-ember font-mono font-bold text-lg shrink-0 w-10 text-center">
                            {ans.nervousness_score}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-mist text-xs mb-0.5">
                              {sess ? `${sess.company} · ${sess.role}` : 'Past session'}
                            </p>
                            <p className="text-chalk text-sm leading-relaxed line-clamp-2">
                              {ans.improvement_tip}
                            </p>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* CTA */}
              <div className="flex flex-col sm:flex-row gap-3 animate-fade-in">
                <button className="btn-primary flex-1" onClick={() => navigate('quickdrill')}>
                  <span className="flex items-center justify-center gap-2">⚡ Quick Drill to Improve</span>
                </button>
                <button className="btn-secondary flex-1" onClick={() => navigate('setup')}>
                  Full Interview →
                </button>
              </div>
            </>
          )}
        </div>
      </main>
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </>
  )
}