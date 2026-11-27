import { useEffect, useRef, useState, type KeyboardEvent } from 'react'

interface ChatInputProps {
  onSend: (text: string) => void
  disabled: boolean
  // Prefill (e.g. a suggestion). Remount with a new `key` to apply a new one.
  initialValue?: string
  // A failed question: its text comes back into the input (if empty) so it
  // isn't lost, and leaves again when the turn is retried or dropped.
  failedTurn: { id: string; text: string } | null
}

export function ChatInput({
  onSend,
  disabled,
  initialValue = '',
  failedTurn,
}: ChatInputProps): React.JSX.Element {
  const [value, setValue] = useState(initialValue)
  const [restored, setRestored] = useState<{ id: string; text: string } | null>(null)
  // Adjust state on prop change during render (no effect, no extra paint).
  if (failedTurn && failedTurn.id !== restored?.id) {
    setRestored(failedTurn)
    if (!value.trim()) setValue(failedTurn.text)
  } else if (!failedTurn && restored) {
    setRestored(null)
    if (value === restored.text) setValue('')
  }
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const wasDisabled = useRef(disabled)

  // Refocus once a pending answer arrives (the disabled textarea lost focus).
  useEffect(() => {
    if (wasDisabled.current && !disabled) textareaRef.current?.focus()
    wasDisabled.current = disabled
  }, [disabled])

  function submit(): void {
    if (!value.trim() || disabled) return
    onSend(value)
    // Cleared while the question bubble shows it; restored if the turn fails.
    setValue('')
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>): void {
    // isComposing: Enter confirms an IME (e.g. Korean) composition, not a send.
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="border-t border-surface-2 p-4">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 rounded-lg bg-surface-2 p-2 shadow-inset-border focus-within:ring-2 focus-within:ring-fg">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            autoFocus={initialValue !== ''}
            rows={1}
            aria-label="Message"
            aria-describedby="chat-input-hint"
            placeholder="Ask anything about your documents…"
            className="field-sizing-content max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-fg outline-none placeholder:text-muted disabled:opacity-50"
          />
          <button
            type="button"
            onClick={submit}
            disabled={disabled || !value.trim()}
            className="btn-primary"
          >
            Send
          </button>
        </div>
        <p id="chat-input-hint" className="mt-1.5 px-2 text-2xs text-muted">
          Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  )
}
