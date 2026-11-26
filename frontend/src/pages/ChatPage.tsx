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

// Sentinel select value for "let the agent pick the collection(s) per query"
// (maps to collection_name: undefined on the wire, see useChat).
const AGENT_CHOOSES_COLLECTION = '__agent_choose__'

export default function ChatPage() {
  const { data: collections, isLoading: collectionsLoading } = useCollections()
  const { data: chatModels, isLoading: chatModelsLoading } = useChatModels()
  // Explicit user choice overrides the default; otherwise fall back to the
  // first available option, same pattern as CreateCollectionForm.
  const [collectionOverride, setCollectionOverride] = useState('')
  const [chatModelOverride, setChatModelOverride] = useState('')

  const collectionSelectValue =
    collectionOverride || collections?.[0]?.name || AGENT_CHOOSES_COLLECTION
  const collectionName =
    collectionSelectValue === AGENT_CHOOSES_COLLECTION ? null : collectionSelectValue
  const chatModel = chatModelOverride || chatModels?.[0]?.name || ''

  const { messages, send, reset, chatId, isThinking } = useChat({
    collectionName,
    chatModel: chatModel || null,
  })
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  const isEmpty = messages.length === 0
  // The server pins chat_model (and collection, if set) at creation time, so
  // once a chat has started the pickers can no longer change anything — lock them.
  const pickersLocked = chatId !== null
  const canChat = chatModel !== ''

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-surface-2 px-6 py-4">
        <h1 className="text-2xl font-bold">Chat</h1>
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Collection"
            value={collectionSelectValue}
            onChange={(e) => setCollectionOverride(e.target.value)}
            disabled={pickersLocked || collectionsLoading}
            className="field w-auto"
          >
            {collectionsLoading ? (
              <option value="">Loading collections…</option>
            ) : (
              <>
                <option value={AGENT_CHOOSES_COLLECTION}>
                  Let the agent choose
                </option>
                {collections?.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name}
                  </option>
                ))}
              </>
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
            className="field w-auto"
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
              className="btn-ghost"
            >
              New chat
            </button>
          )}
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {isEmpty ? (
          <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center text-center">
            <span className="mb-4 grid size-14 place-items-center rounded-full bg-surface-2 text-3xl">
              💬
            </span>
            <h2 className="text-2xl font-bold">
              Ask your knowledge base
            </h2>
            <p className="mt-1 text-sm text-muted">
              Answers are grounded in your uploaded documents.
            </p>
            {canChat ? (
              <div className="mt-6 grid w-full gap-2 sm:grid-cols-3">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => send(s)}
                    className="rounded-lg bg-surface p-3 text-left text-sm text-soft transition hover:bg-surface-3 hover:text-fg focus-visible:outline-2 focus-visible:outline-fg"
                  >
                    {s}
                  </button>
                ))}
              </div>
            ) : (
              <p className="mt-6 text-sm text-muted">
                Pick a chat model above to get started.
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
                <div className="rounded-lg bg-surface px-4 py-3 text-sm text-muted">
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
