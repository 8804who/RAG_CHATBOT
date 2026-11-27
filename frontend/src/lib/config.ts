// Base URL for the backend API. Empty string means same-origin, which works in
// dev via the Vite proxy (see vite.config.ts) and in prod when served together.
export const API_BASE = import.meta.env.VITE_API_BASE ?? ''

// Document upload: text-only (files are read as text and sent as JSON), with a
// client-side size cap so a huge file fails fast instead of mid-request.
export const UPLOAD_EXTENSIONS = ['.md', '.markdown', '.txt']
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024
