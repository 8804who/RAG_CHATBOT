import { API_BASE } from '../config'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// The backend error format is `{ "detail": string }` (422 validation errors
// carry a list instead, which falls back to the generic message).
async function errorMessage(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json()
    if (
      typeof body === 'object' &&
      body !== null &&
      'detail' in body &&
      typeof body.detail === 'string'
    ) {
      return body.detail
    }
  } catch {
    // Non-JSON error body: use the generic message.
  }
  return `Request failed (error ${res.status})`
}

/** Fetch with the session cookie; throws ApiError on a non-2xx status. The body is unread. */
export async function apiResponse(path: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers)
  if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json')

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'include',
    headers,
  })

  if (!res.ok) {
    throw new ApiError(res.status, await errorMessage(res))
  }
  return res
}

/** Thin fetch wrapper for real backend calls. Sends cookies for the session. */
export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await apiResponse(path, options)

  // 204 No Content (e.g. logout) has no body.
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}
