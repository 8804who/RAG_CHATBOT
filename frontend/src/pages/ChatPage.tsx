import { useEffect, useRef } from 'react'

import ChatInput from '../components/chat/ChatInput'
import MessageBubble from '../components/chat/MessageBubble'
import { useChat } from '../hooks/useChat'

const suggestions = [
  'Summarize the employee handbook',
  'What are the Q1 engineering priorities?',
  'What does the security policy say about passwords?',
]

export default function ChatPage() {
  const { messages, send, reset, isThinking } = useChat()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  const isEmpty = messages.length === 0

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4">
        <h1 className="text-lg font-semibold">Chat</h1>
        {!isEmpty && (
          <button
            type="button"
            onClick={reset}
            className="rounded-lg px-3 py-1.5 text-sm text-gray-500 hover:bg-gray-100"
          >
            New chat
          </button>
        )}
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {isEmpty ? (
          <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center text-center">
            <span className="mb-4 grid size-14 place-items-center rounded-2xl bg-brand-50 text-3xl">
              💬
            </span>
            <h2 className="text-xl font-semibold text-gray-900">
              Ask your knowledge base
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              Answers are grounded in your uploaded documents.
            </p>
            <div className="mt-6 grid w-full gap-2 sm:grid-cols-3">
              {suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-xl border border-gray-200 bg-white p-3 text-left text-sm text-gray-600 transition hover:border-brand-300 hover:bg-brand-50"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-6">
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
            {isThinking && (
              <div className="flex justify-start">
                <div className="rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-400">
                  Thinking…
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <ChatInput onSend={send} disabled={isThinking} />
    </div>
  )
}
