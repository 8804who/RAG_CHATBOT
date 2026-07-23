export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let i = 0
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i++
  }
  return `${value.toFixed(1)} ${units[i]}`
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export function formatSecondsRemaining(seconds: number): string {
  if (seconds < 10) return 'a few seconds left'
  if (seconds < 60) return `~${Math.round(seconds / 5) * 5}s left`
  const minutes = Math.round(seconds / 60)
  return `~${minutes}m left`
}
