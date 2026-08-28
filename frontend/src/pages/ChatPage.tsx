import { useEffect, useRef, useState } from 'react'

import ChatInput from '../components/chat/ChatInput'
import MessageBubble from '../components/chat/MessageBubble'
import { useChat } from '../hooks/useChat'
import { useCollections } from '../hooks/useCollections'
import { useChatModels } from '../hooks/useModels'

const suggestions = [
  'Summarize the employee handbook',
  'What are the Q1 engineering priorities?',
  'What does the security policy say about passwords?',
]

const selectClass =
  'rounded-lg border border-gray-300 bg-white px-2.5 py-1.5 text-sm outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-100 disabled:opacity-50'

export default function ChatPage() {
  const { data: collections, isLoading: collectionsLoading } = useCollections()
  const { data: chatModels, isLoading: chatModelsLoading } = useChatModels()
  // Explicit user choice overrides the default; otherwise fall back to the
  // first available option, same pattern as CreateCollectionForm.
  const [collectionOverride, setCollectionOverride] = useState('')
  const [chatModelOverride, setChatModelOverride] = useState('')

  const collectionName = collectionOverride || collections?.[0]?.name || ''
  const chatModel = chatModelOverride || chatModels?.[0]?.name || ''

  const { messages, send, reset, chatId, isThinking } = useChat({
    collectionName: collectionName || null,
    chatModel: chatModel || null,
  })
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  const isEmpty = messages.length === 0
  // The server pins collection + chat_model at creation time, so once a chat
  // has started the pickers can no longer change anything — lock them.
  const pickersLocked = chatId !== null
  const canChat = collectionName !== '' && chatModel !== ''

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 bg-white px-6 py-4">
        <h1 className="text-lg font-semibold">Chat</h1>
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Collection"
            value={collectionName}
            onChange={(e) => setCollectionOverride(e.target.value)}
            disabled={
              pickersLocked ||
              collectionsLoading ||
              !collections ||
              collections.length === 0
            }
            className={selectClass}
          >
            {collectionsLoading ? (
              <option value="">Loading collections…</option>
            ) : !collections || collections.length === 0 ? (
              <option value="">No collections</option>
            ) : (
              collections.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))
            )}
          </select>
          <select
            aria-label="Chat model"
            value={chatModel}
            onChange={(e) => setChatModelOverride(e.target.value)}
            disabled={
              pickersLocked ||
              chatModelsLoading ||
              !chatModels ||
              chatModels.length === 0
            }
            className={selectClass}
          >
            {chatModelsLoading ? (
              <option value="">Loading models…</option>
            ) : !chatModels || chatModels.length === 0 ? (
              <option value="">No models</option>
            ) : (
              chatModels.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name}
                </option>
              ))
            )}
          </select>
          {!isEmpty && (
            <button
              type="button"
              onClick={reset}
              className="rounded-lg px-3 py-1.5 text-sm text-gray-500 hover:bg-gray-100"
            >
              New chat
            </button>
          )}
        </div>
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
            {canChat ? (
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
            ) : (
              <p className="mt-6 text-sm text-gray-400">
                Pick a collection and a chat model above to get started.
              </p>
            )}
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

      <ChatInput onSend={send} disabled={isThinking || !canChat} />
    </div>
  )
}
