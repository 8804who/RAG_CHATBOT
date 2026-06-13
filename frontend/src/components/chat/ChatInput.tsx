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
    <div className="border-t border-gray-200 bg-white p-4">
      <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-gray-300 bg-white p-2 focus-within:border-brand-400">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Ask anything about your documents…"
          className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none"
        />
        <button
          type="button"
          onClick={submit}
          disabled={disabled || !value.trim()}
          className="rounded-xl bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-40"
        >
          Send
        </button>
      </div>
    </div>
  )
}
