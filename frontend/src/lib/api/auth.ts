import { API_BASE } from '../config'
import type { User } from '../types'
import { apiFetch } from './client'

/**
 * Start login by redirecting the browser to the backend's Google OAuth route.
 * The backend redirects to Google and back to the callback, which sets the
 * session cookie and returns to the frontend. This navigates away, so any code
 * after it does not run.
 */
export async function startLogin(): Promise<void> {
  window.location.href = `${API_BASE}/api/v1/auth/google/login`
}

/** Resolve the current user from the session cookie, or null if unauthenticated. */
export async function getCurrentUser(): Promise<User | null> {
  try {
    return await apiFetch<User>('/api/v1/auth/me')
  } catch {
    return null
  }
}

export async function logout(): Promise<void> {
  await apiFetch<void>('/api/v1/auth/google/logout', { method: 'POST' })
}
