import React, { useState } from 'react'
import { api } from '../lib/api'
import { NavBar, Toggle, Spinner, Toast } from '../components/UI'
import { Briefcase, Zap } from 'lucide-react'

const ROUNDS = ['First Round', 'Technical', 'HR', 'Final Round', 'Case Study']
const PERSONAS = ['Friendly', 'Neutral', 'Tough', 'Stress Test']

export default function SetupPage({ navigate, onSignOut, user }) {
  const [form, setForm]       = useState({
    company: '',
    role: '',
    round: ROUNDS[0],
    first_time: false,
    distraction_enabled: false,
    persona: PERSONAS[1],
  })
  const [loading, setLoading] = useState(false)
  const [toast, setToast]     = useState(null)

  const set = (key, val) => setForm(f => ({ ...f, [key]: val }))

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.company.trim() || !form.role.trim()) {
      return setToast({ message: 'Company and role are required', type: 'error' })
    }
    setLoading(true)
    try {
      // 1. Create session
      const { session_id } = await api.createSession({
        company: form.company,
        role: form.role,
        round: form.round,
        first_time: form.first_time,
        distraction_enabled: form.distraction_enabled,
        persona: form.persona,
      })

      // 2. Generate questions
      await api.generateQuestions({
        session_id,
        company: form.company,
        role: form.role,
        round: form.round,
        first_time: form.first_time,
        persona: form.persona,
      })

      // 3. Navigate to interview
      navigate('interview', { sessionId: session_id, distractionEnabled: form.distraction_enabled })
    } catch (err) {
      setToast({ message: err.message, type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <NavBar onSignOut={onSignOut} userName={user?.email} />
      <main className="min-h-screen bg-obsidian px-4 py-8 md:px-8">
        <div className="max-w-xl mx-auto">

          <div className="mb-8 animate-fade-in">
            <p className="text-mist text-xs uppercase tracking-widest font-mono mb-1">New Session</p>
            <h1 className="heading-display text-5xl gradient-text">Set the Stage</h1>
            <p className="text-mist mt-2 text-sm">Tell us about the interview and we'll generate tailored questions.</p>
          </div>

          <form onSubmit={handleSubmit} className="card flex flex-col gap-6 animate-slide-up">

            <div>
              <label className="label">Company name</label>
              <input
                className="input"
                placeholder="e.g. Google, Infosys, Startup XYZ"
                value={form.company}
                onChange={e => set('company', e.target.value)}
                required
              />
            </div>

            <div>
              <label className="label">Role / Position</label>
              <input
                className="input"
                placeholder="e.g. Software Engineer, Product Manager"
                value={form.role}
                onChange={e => set('role', e.target.value)}
                required
              />
            </div>

            <div>
              <label className="label">Interview Round</label>
              <select
                className="input appearance-none"
                value={form.round}
                onChange={e => set('round', e.target.value)}
              >
                {ROUNDS.map(r => <option key={r}>{r}</option>)}
              </select>
            </div>

            <div>
              <label className="label">Interviewer Persona</label>
              <select
                className="input appearance-none"
                value={form.persona}
                onChange={e => set('persona', e.target.value)}
              >
                {PERSONAS.map(p => <option key={p}>{p}</option>)}
              </select>
            </div>

            <div className="flex items-center justify-between py-2 border-t border-steel">
              <div>
                <p className="text-chalk text-sm font-medium">First time at this company?</p>
                <p className="text-mist text-xs">Questions will be more introductory</p>
              </div>
              <Toggle
                checked={form.first_time}
                onChange={v => set('first_time', v)}
              />
            </div>

            <div className="flex items-center justify-between py-2 border-t border-steel">
              <div className="flex items-start gap-2">
                <Zap size={16} className="text-amber mt-0.5 shrink-0" />
                <div>
                  <p className="text-chalk text-sm font-medium">Distraction Mode</p>
                  <p className="text-mist text-xs">Surprise interruptions simulate real interview stress</p>
                </div>
              </div>
              <Toggle
                checked={form.distraction_enabled}
                onChange={v => set('distraction_enabled', v)}
              />
            </div>

            <button
              className="btn-primary w-full flex items-center justify-center gap-2 text-base py-4"
              disabled={loading}
            >
              {loading ? (
                <>
                  <Spinner className="w-5 h-5" />
                  <span>Generating questions…</span>
                </>
              ) : (
                <>
                  <Briefcase size={18} />
                  Start Interview Prep →
                </>
              )}
            </button>
          </form>
        </div>
      </main>

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </>
  )
}
