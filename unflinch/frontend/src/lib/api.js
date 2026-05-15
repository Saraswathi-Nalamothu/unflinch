/**
 * Unflinch API client
 * Wraps all backend requests with the Supabase JWT.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function getToken() {
  const { data } = await import('./supabase').then(m =>
    m.supabase.auth.getSession()
  )
  return data?.session?.access_token || null
}

async function apiFetch(path, options = {}) {
  const token = await getToken()
  const headers = {
    ...(options.headers || {}),
    Authorization: `Bearer ${token}`,
  }
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'API error')
  }
  return res.json()
}

// ── Endpoints ────────────────────────────────────────────────

export const api = {
  createSession: (body) =>
    apiFetch('/create_session', { method: 'POST', body: JSON.stringify(body) }),

  generateQuestions: (body) =>
    apiFetch('/generate_questions', { method: 'POST', body: JSON.stringify(body) }),

  analyzeAnswer: (formData) =>
    apiFetch('/analyze_answer', { method: 'POST', body: formData }),

  getSession: (sessionId) =>
    apiFetch(`/get_session/${sessionId}`),

  getDashboard: () =>
    apiFetch('/dashboard'),

  saveSession: (sessionId) =>
    apiFetch('/save_session', { method: 'POST', body: JSON.stringify({ session_id: sessionId }) }),

  generateImprovementPlan: (sessionId) =>
    apiFetch('/generate_improvement_plan', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId }),
    }),
}
