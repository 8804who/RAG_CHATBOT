import { useEffect, useState } from 'react'

const SLOW_AFTER_SECONDS = 8

/** Pending-answer indicator with an elapsed counter; mount it only while waiting. */
export function ThinkingIndicator(): React.JSX.Element {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="flex justify-start">
      <div
        role="status"
        className="rounded-lg bg-surface px-4 py-3 text-sm text-muted"
      >
        <p>
          Thinking…{' '}
          <span aria-hidden="true" className="tabular-nums">
            {seconds}s
          </span>
        </p>
        {seconds >= SLOW_AFTER_SECONDS && (
          <p className="mt-1 text-xs">
            Still working… searching your documents can take up to a minute.
          </p>
        )}
      </div>
    </div>
  )
}
