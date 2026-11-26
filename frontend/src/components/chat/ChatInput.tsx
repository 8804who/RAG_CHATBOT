import { useState, type KeyboardEvent } from 'react'

interface ChatInputProps {
  onSend: (text: string) => void
  disabled?: boolean
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState('')

  function submit() {
    if (!value.trim() || disabled) return
    onSend(value)
    setValue('')
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="border-t border-surface-2 p-4">
      <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-lg bg-surface-2 p-2 shadow-inset-border focus-within:ring-2 focus-within:ring-fg">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Ask anything about your documents…"
          className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-fg outline-none placeholder:text-muted"
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
    </div>
  )
}
