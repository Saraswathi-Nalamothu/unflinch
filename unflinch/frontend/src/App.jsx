import React from 'react'
import { useAuth } from './hooks/useAuth'
import AuthPage     from './pages/AuthPage'
import DashboardPage from './pages/DashboardPage'
import SetupPage    from './pages/SetupPage'
import InterviewPage from './pages/InterviewPage'
import SummaryPage  from './pages/SummaryPage'
import { Spinner }  from './components/UI'

/**
 * Minimal client-side router using React state.
 * Pages: 'auth' | 'dashboard' | 'setup' | 'interview' | 'summary'
 */
export default function App() {
  const { session, user, loading, signOut } = useAuth()
  const [page, setPage]   = React.useState('dashboard')
  const [params, setParams] = React.useState({})

  function navigate(to, p = {}) {
    setPage(to)
    setParams(p)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Loading state while Supabase session resolves
  if (loading) {
    return (
      <div className="min-h-screen bg-obsidian flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <span className="heading-display text-4xl gradient-text animate-pulse-slow">UNFLINCH</span>
          <Spinner className="w-6 h-6 text-mist" />
        </div>
      </div>
    )
  }

  // Not authenticated → show auth
  if (!session) return <AuthPage />

  const shared = { navigate, onSignOut: signOut, user }

  switch (page) {
    case 'setup':
      return <SetupPage     {...shared} />
    case 'interview':
      return <InterviewPage {...shared} params={params} />
    case 'summary':
      return <SummaryPage   {...shared} params={params} />
    case 'dashboard':
    default:
      return <DashboardPage {...shared} />
  }
}
