// Base URL for the backend API. Empty string means same-origin, which works in
// dev via the Vite proxy (see vite.config.ts) and in prod when served together.
export const API_BASE = import.meta.env.VITE_API_BASE ?? ''

// When true (default), chat and document calls return in-memory mock data so the
// app runs standalone. Flip to "false" once the backend implements those routes.
export const USE_MOCKS = (import.meta.env.VITE_USE_MOCKS ?? 'true') !== 'false'

export const delay = (ms: number) => new Promise((r) => setTimeout(r, ms))
