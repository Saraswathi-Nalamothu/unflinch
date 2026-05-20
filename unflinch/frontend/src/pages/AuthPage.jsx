import React, { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { Spinner, Toast } from '../components/UI'

function mapAuthError(err) {
  const msg = err?.message ?? ''
  const code = err?.code ?? ''
  if (code === 'user_already_exists' || /already registered/i.test(msg)) {
    return 'This email is already registered. Try signing in instead.'
  }
  if (code === 'invalid_credentials' || /invalid login credentials/i.test(msg)) {
    return 'Invalid email or password. Please try again.'
  }
  if (code === 'email_not_confirmed') {
    return 'Please confirm your email before signing in.'
  }
  if (/password/i.test(msg) && /weak|short/i.test(msg)) {
    return 'Password must be at least 6 characters.'
  }
  return msg || 'Something went wrong. Please try again.'
}

function GoogleIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
    </svg>
  )
}

export default function AuthPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)

  const showToast = useCallback((message, type = 'info') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 4500)
  }, [])

  async function handleEmailSubmit(e) {
    e.preventDefault()
    if (password.length < 6) {
      showToast('Password must be at least 6 characters', 'error')
      return
    }
    if (mode === 'signup' && password !== confirmPassword) {
      showToast('Passwords do not match', 'error')
      return
    }

    setLoading(true)
    try {
      if (mode === 'signup') {
        const { data, error } = await supabase.auth.signUp({ email, password })
        if (error) throw error
        if (data.session) {
          showToast('Account created. Welcome!', 'success')
          navigate('/dashboard')
        } else {
          showToast('Check your email to confirm your account', 'info')
        }
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
        showToast('Welcome back!', 'success')
        navigate('/dashboard')
      }
    } catch (err) {
      showToast(mapAuthError(err), 'error')
    } finally {
      setLoading(false)
    }
  }

  async function handleGoogleSignIn() {
    setLoading(true)
    try {
      const { error } = await supabase.auth.signInWithOAuth({ provider: 'google' })
      if (error) throw error
    } catch (err) {
      showToast(mapAuthError(err), 'error')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-obsidian flex flex-col items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm animate-slide-up">
        <div className="text-center mb-10">
          <h1 className="heading-display text-6xl gradient-text mb-2">UNFLINCH</h1>
          <p className="text-mist text-sm">AI Interview Prep · Voice Analysis · Real Feedback</p>
        </div>

        <div className="card">
          <div className="flex mb-6 bg-carbon rounded-xl p-1">
            <button
              type="button"
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all duration-200
                ${mode === 'login' ? 'bg-graphite text-chalk' : 'text-mist'}`}
              onClick={() => setMode('login')}
              disabled={loading}
            >
              Sign In
            </button>
            <button
              type="button"
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all duration-200
                ${mode === 'signup' ? 'bg-graphite text-chalk' : 'text-mist'}`}
              onClick={() => setMode('signup')}
              disabled={loading}
            >
              Sign Up
            </button>
          </div>

          <form onSubmit={handleEmailSubmit} className="flex flex-col gap-4">
            <div>
              <label className="label" htmlFor="auth-email">Email</label>
              <input
                id="auth-email"
                className="input"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                autoFocus
                disabled={loading}
              />
            </div>
            <div>
              <label className="label" htmlFor="auth-password">Password</label>
              <input
                id="auth-password"
                className="input"
                type="password"
                placeholder="minimum 6 characters"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                minLength={6}
                disabled={loading}
              />
            </div>
            {mode === 'signup' && (
              <div>
                <label className="label" htmlFor="auth-confirm">Confirm password</label>
                <input
                  id="auth-confirm"
                  className="input"
                  type="password"
                  placeholder="repeat password"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  required
                  minLength={6}
                  disabled={loading}
                />
              </div>
            )}
            <button
              type="submit"
              className="btn-primary w-full flex items-center justify-center gap-2 mt-1"
              disabled={loading}
            >
              {loading ? <Spinner className="w-4 h-4" /> : mode === 'login' ? 'Sign In →' : 'Create Account →'}
            </button>
          </form>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-steel" />
            </div>
            <div className="relative flex justify-center text-xs uppercase tracking-widest">
              <span className="bg-graphite px-3 text-mist">or</span>
            </div>
          </div>

          <button
            type="button"
            onClick={handleGoogleSignIn}
            disabled={loading}
            className="btn-secondary w-full flex items-center justify-center gap-3"
          >
            <GoogleIcon />
            Continue with Google
          </button>
        </div>
      </div>

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
