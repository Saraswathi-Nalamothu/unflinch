import React, { useState } from 'react'
import { supabase } from '../lib/supabase'
import { Spinner, Toast } from '../components/UI'
import { Mail, Lock } from 'lucide-react'

export default function AuthPage() {
  const [mode, setMode]         = useState('login')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
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

  async function handleGoogleSignIn() {
    setGoogleLoading(true)
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: 'https://unflinch.vercel.app',
        },
      })
      if (error) throw error
    } catch (err) {
      showToast(err.message || 'Google sign in failed', 'error')
      setGoogleLoading(false)
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

          {/* Google Sign In */}
          <button
            onClick={handleGoogleSignIn}
            disabled={googleLoading}
            className="w-full flex items-center justify-center gap-3 bg-white hover:bg-gray-50
                       text-gray-700 font-medium py-3 px-4 rounded-xl transition-all duration-200
                       active:scale-95 disabled:opacity-50 mb-4"
          >
            {googleLoading ? (
              <Spinner className="w-4 h-4 text-gray-500" />
            ) : (
              <svg width="18" height="18" viewBox="0 0 18 18">
                <path fill="#4285F4" d="M16.51 8H8.98v3h4.3c-.18 1-.74 1.48-1.6 2.04v2.01h2.6a7.8 7.8 0 0 0 2.38-5.88c0-.57-.05-.66-.15-1.18z"/>
                <path fill="#34A853" d="M8.98 17c2.16 0 3.97-.72 5.3-1.94l-2.6-2.04a4.8 4.8 0 0 1-7.18-2.54H1.83v2.07A8 8 0 0 0 8.98 17z"/>
                <path fill="#FBBC05" d="M4.5 10.48A4.8 4.8 0 0 1 4.5 7.5V5.43H1.83a8 8 0 0 0 0 7.14l2.67-2.09z"/>
                <path fill="#EA4335" d="M8.98 3.58c1.32 0 2.5.45 3.44 1.35l2.56-2.56A8 8 0 0 0 1.83 5.43L4.5 7.5a4.77 4.77 0 0 1 4.48-3.92z"/>
              </svg>
            )}
            <span>{googleLoading ? 'Redirecting...' : 'Continue with Google'}</span>
          </button>

          {/* Divider */}
          <div className="flex items-center gap-3 mb-4">
            <div className="flex-1 h-px bg-steel" />
            <span className="text-mist text-xs">or</span>
            <div className="flex-1 h-px bg-steel" />
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