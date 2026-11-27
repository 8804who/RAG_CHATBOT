/** Client-side id for list keys and optimistic items (not sent to the server). */
export function uid(): string {
  // randomUUID exists only in secure contexts (HTTPS/localhost); plain-HTTP
  // deploys fall back to getRandomValues, which works everywhere.
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) =>
    b.toString(16).padStart(2, '0'),
  ).join('')
}
