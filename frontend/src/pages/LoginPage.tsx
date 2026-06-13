import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'

export default function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/chat" replace />

  async function handleLogin() {
    setBusy(true)
    try {
      await login()
      navigate('/chat', { replace: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-full items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="mb-3 grid size-12 place-items-center rounded-xl bg-brand-500 text-2xl text-white">
            ◆
          </span>
          <h1 className="text-xl font-semibold text-gray-900">RAG Chatbot</h1>
          <p className="mt-1 text-sm text-gray-500">
            Sign in to chat with your documents
          </p>
        </div>

        <button
          type="button"
          onClick={handleLogin}
          disabled={busy}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:opacity-60"
        >
          <GoogleIcon />
          {busy ? 'Signing in…' : 'Continue with Google'}
        </button>
      </div>
    </div>
  )
}

function GoogleIcon() {
  return (
    <svg className="size-5" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.99.66-2.26 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"
      />
    </svg>
  )
}
