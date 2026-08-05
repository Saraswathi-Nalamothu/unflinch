import React, { useState } from 'react'
import { supabase } from '../lib/supabase'
import { Spinner, Toast } from '../components/UI'
import { Mail, Lock } from 'lucide-react'

export default function AuthPage() {
  const [mode, setMode]         = useState('login')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const [toast, setToast]       = useState(null)

  const showToast = (message, type = 'info') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 4000)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (password.length < 6) return showToast('Password must be at least 6 characters', 'error')
    setLoading(true)
    try {
      if (mode === 'signup') {
        const { error } = await supabase.auth.signUp({ email, password })
        if (error) throw error
        showToast('Account created! You are now logged in.', 'success')
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
      }
    } catch (err) {
      showToast(err.message || 'Something went wrong', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-obsidian flex flex-col items-center justify-center px-4">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-96 h-96 bg-ember/5 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-sm relative z-10 animate-slide-up">
        {/* Logo */}
        <div className="text-center mb-10">
          <h1 className="heading-display text-6xl gradient-text mb-2">UNFLINCH</h1>
          <p className="text-mist text-sm">AI Interview Prep · Voice Analysis · Real Feedback</p>
        </div>

        <div className="card">
          {/* Tab switcher */}
          <div className="flex mb-6 bg-carbon rounded-xl p-1">
            <button
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all duration-200
                ${mode === 'login' ? 'bg-graphite text-chalk' : 'text-mist hover:text-chalk'}`}
              onClick={() => setMode('login')}
            >Sign In</button>
            <button
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all duration-200
                ${mode === 'signup' ? 'bg-graphite text-chalk' : 'text-mist hover:text-chalk'}`}
              onClick={() => setMode('signup')}
            >Sign Up</button>
          </div>

          {/* Email form */}
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="label">Email</label>
              <div className="relative">
                <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-mist" />
                <input className="input pl-9" type="email" placeholder="you@example.com"
                  value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
              </div>
            </div>
            <div>
              <label className="label">Password</label>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-mist" />
                <input className="input pl-9" type="password" placeholder="minimum 6 characters"
                  value={password} onChange={e => setPassword(e.target.value)} required />
              </div>
            </div>
            <button className="btn-primary w-full flex items-center justify-center gap-2 mt-2" disabled={loading}>
              {loading ? <Spinner className="w-4 h-4" /> : mode === 'login' ? 'Sign In →' : 'Create Account →'}
            </button>
          </form>
        </div>

        <p className="text-center text-mist/60 text-xs mt-6">
          By continuing, you agree to practise interviews without flinching.
        </p>
      </div>

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}