import { API_BASE } from '../config'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Thin fetch wrapper for real backend calls. Sends cookies for the session. */
export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })

  if (!res.ok) {
    throw new ApiError(res.status, `Request failed: ${res.status}`)
  }

  // 204 No Content (e.g. logout) has no body.
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}
