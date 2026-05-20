import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import AuthPage from './pages/AuthPage'
import DashboardPage from './pages/DashboardPage'
import SetupPage from './pages/SetupPage'
import InterviewPage from './pages/InterviewPage'
import SummaryPage from './pages/SummaryPage'
import { Spinner } from './components/UI'

function AuthenticatedApp({ user, signOut, page, params, navigate }) {
  const shared = { navigate, onSignOut: signOut, user }

  switch (page) {
    case 'setup':
      return <SetupPage {...shared} />
    case 'interview':
      return <InterviewPage {...shared} params={params} />
    case 'summary':
      return <SummaryPage {...shared} params={params} />
    case 'dashboard':
    default:
      return <DashboardPage {...shared} />
  }
}

export default function App() {
  const { session, user, loading, signOut } = useAuth()
  const [page, setPage] = React.useState('dashboard')
  const [params, setParams] = React.useState({})

  function navigate(to, p = {}) {
    setPage(to)
    setParams(p)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

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

  return (
    <Routes>
      <Route
        path="/"
        element={session ? <Navigate to="/dashboard" replace /> : <AuthPage />}
      />
      <Route
        path="/dashboard"
        element={
          session ? (
            <AuthenticatedApp
              user={user}
              signOut={signOut}
              navigate={navigate}
              page={page}
              params={params}
            />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route
        path="*"
        element={<Navigate to={session ? '/dashboard' : '/'} replace />}
      />
    </Routes>
  )
}
