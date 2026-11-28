import { useEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { Link, useLocation, useParams } from 'react-router-dom'

import { ChatInput } from '../components/chat/ChatInput'
import { ChatListPanel } from '../components/chat/ChatListPanel'
import { MessageBubble } from '../components/chat/MessageBubble'
import { ThinkingIndicator } from '../components/chat/ThinkingIndicator'
import { useChat } from '../hooks/useChat'
import { useCollections } from '../hooks/useCollections'
import { useChatModels } from '../hooks/useModels'
import { ApiError } from '../lib/api/client'

const suggestions = [
  'What topics do my documents cover?',
  'Summarize the key points of my documents',
  'What should I read first?',
]

// Sentinel select value for "let the agent pick the collection(s) per query"
// (maps to collection_name: undefined on the wire, see useChat).
const AGENT_CHOOSES_COLLECTION = '__agent_choose__'

const linkClass = 'font-bold text-fg underline'

// UI copy by status. Server `detail` is not shown: it may be in another
// language or carry internal ids (KI-058).
function turnErrorText(err: Error): string {
  const status = err instanceof ApiError ? err.status : 0
  if (status === 409) {
    return 'Still answering your previous message. Wait a moment, then retry.'
  }
  if (status === 401) return 'Your session has expired. Sign in again, then retry.'
  if (status === 400) {
    return "The selected model or collection isn't available anymore. Start a new chat and pick another."
  }
  return "Couldn't get an answer right now. Your message wasn't saved; retry to send it again."
}

function isUnavailable(err: Error | null): boolean {
  return err instanceof ApiError && (err.status === 403 || err.status === 404)
}

export function ChatPage(): React.JSX.Element {
  const { chatId = null } = useParams()
  const { pathname } = useLocation()
  // Below lg the chat list is an overlay, open only for the path it was opened
  // on, so picking a chat (a route change) closes it without an effect.
  const [listOpenOnPath, setListOpenOnPath] = useState<string | null>(null)
  const listOpen = listOpenOnPath === pathname
  const listButtonRef = useRef<HTMLButtonElement>(null)
  const listCloseRef = useRef<HTMLButtonElement>(null)
  const collectionsQuery = useCollections()
  const collections = collectionsQuery.data
  const { data: chatModels, isLoading: chatModelsLoading } = useChatModels()
  const [collectionOverride, setCollectionOverride] = useState('')
  const [chatModelOverride, setChatModelOverride] = useState('')
  // A suggestion click remounts ChatInput (new key) prefilled with its text.
  const [draft, setDraft] = useState({ key: 0, text: '' })

  // Overrides that no longer exist (deleted elsewhere) fall back to the default.
  const collectionName = collections?.some((c) => c.name === collectionOverride)
    ? collectionOverride
    : null
  const chatModel = chatModels?.some((m) => m.name === chatModelOverride)
    ? chatModelOverride
    : (chatModels?.[0]?.name ?? '')

  const chat = useChat({ chatId, collectionName, chatModel: chatModel || null })
  const { messages, history, isThinking, isStreaming } = chat

  const lastMessageRef = useRef<HTMLDivElement>(null)
  const lastMessageId = messages.at(-1)?.id
  // Bring the start of the newest message (a fresh answer) into view.
  useEffect(() => {
    if (!lastMessageId) return
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    lastMessageRef.current?.scrollIntoView({
      block: 'start',
      behavior: reduceMotion ? 'auto' : 'smooth',
    })
  }, [lastMessageId])

  const unavailable = isUnavailable(chat.historyError) || isUnavailable(chat.error)
  // The server pins the model (and collection) at creation, so pickers lock
  // once a chat exists or its first message is on the way.
  const pickersLocked = chatId !== null || isThinking
  const canSend = chatId ? history !== undefined : chatModel !== ''
  const lockedCollection = chatId ? history?.collectionName : collectionName
  const lockedModel = chatId ? history?.chatModel : chatModel

  // Same overlay pattern as Layout's drawer: focus in on open, Escape closes.
  useEffect(() => {
    if (!listOpen) return
    listCloseRef.current?.focus()
    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key === 'Escape') closeList()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [listOpen])

  // Focus goes back to the Chats button (a no-op at lg+, where it is hidden).
  function closeList(): void {
    flushSync(() => setListOpenOnPath(null))
    listButtonRef.current?.focus()
  }

  function startNewChat(): void {
    closeList()
    chat.reset()
  }

  function renderBody(): React.JSX.Element {
    if (unavailable) {
      return (
        <div role="alert" className="mx-auto max-w-2xl rounded-lg bg-negative/10 p-4 text-sm text-negative">
          <p>This conversation isn't available. It may have been removed or belong to another account.</p>
          <button type="button" onClick={chat.reset} className="btn-secondary mt-3">
            New chat
          </button>
        </div>
      )
    }
    if (chat.historyError) {
      return (
        <div role="alert" className="mx-auto max-w-2xl rounded-lg bg-negative/10 p-4 text-sm text-negative">
          <p>Couldn't load this conversation. Check your connection, then retry.</p>
          <button type="button" onClick={chat.refetchHistory} className="btn-secondary mt-3">
            Retry
          </button>
        </div>
      )
    }
    if (chat.historyLoading) {
      return (
        <p role="status" className="mx-auto max-w-3xl text-sm text-muted">
          Loading conversation…
        </p>
      )
    }
    if (messages.length === 0) {
      return (
        <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center text-center">
          <span aria-hidden="true" className="mb-4 grid size-14 place-items-center rounded-full bg-surface-2 text-3xl">
            💬
          </span>
          <h2 className="text-2xl font-bold">Ask your knowledge base</h2>
          <p className="mt-1 text-sm text-muted">
            Answers are grounded in your uploaded documents.
          </p>
          {collectionsQuery.isError ? (
            <p className="mt-4 text-sm text-muted">
              Couldn't load your collections. Check{' '}
              <Link to="/collections" className={linkClass}>Collections</Link> or{' '}
              <Link to="/documents" className={linkClass}>Documents</Link>.
            </p>
          ) : collections?.length === 0 ? (
            <p className="mt-4 text-sm text-muted">
              No documents yet. Create a collection in{' '}
              <Link to="/collections" className={linkClass}>Collections</Link>, then upload files in{' '}
              <Link to="/documents" className={linkClass}>Documents</Link>.
            </p>
          ) : null}
          {canSend ? (
            <div className="mt-6 grid w-full gap-2 sm:grid-cols-3">
              {suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setDraft((d) => ({ key: d.key + 1, text: s }))}
                  className="min-h-11 rounded-lg bg-surface p-3 text-left text-sm text-soft transition hover:bg-surface-3 hover:text-fg focus-visible:outline-2 focus-visible:outline-fg"
                >
                  {s}
                </button>
              ))}
            </div>
          ) : (
            !chatId && (
              <p className="mt-6 text-sm text-muted">
                Pick a chat model above to get started.
              </p>
            )
          )}
        </div>
      )
    }
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        {messages.map((m, i) => (
          <div
            key={m.id}
            ref={i === messages.length - 1 ? lastMessageRef : undefined}
            className="scroll-mt-6"
          >
            <MessageBubble message={m} />
          </div>
        ))}
        {isThinking && !isStreaming && <ThinkingIndicator />}
        {chat.error && (
          <div role="alert" className="rounded-lg bg-negative/10 p-4 text-sm text-negative">
            <p>{turnErrorText(chat.error)}</p>
            <button type="button" onClick={chat.retry} className="btn-secondary mt-3">
              Retry
            </button>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="relative flex h-full">
      <aside
        id="chat-list"
        role={listOpen ? 'dialog' : undefined}
        aria-modal={listOpen || undefined}
        aria-label={listOpen ? 'Chats' : undefined}
        className={`${listOpen ? 'flex' : 'hidden'} absolute inset-0 z-20 flex-col bg-surface lg:static lg:flex lg:w-64 lg:shrink-0 lg:border-r lg:border-surface-2`}
      >
        <div className="flex items-center justify-between px-4 pt-3 lg:hidden">
          <h2 className="text-lg font-bold">Chats</h2>
          <button
            ref={listCloseRef}
            type="button"
            onClick={closeList}
            aria-label="Close chat list"
            className="grid size-11 place-items-center rounded-full text-muted transition hover:bg-surface-3 hover:text-fg focus-visible:outline-2 focus-visible:outline-fg"
          >
            <span aria-hidden>✕</span>
          </button>
        </div>
        <ChatListPanel
          activeChatId={chatId}
          onNewChat={startNewChat}
          onSelect={closeList}
        />
      </aside>

      <div inert={listOpen} className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-surface-2 px-6 py-4">
          <div className="flex items-center gap-2">
            <button
              ref={listButtonRef}
              type="button"
              onClick={() => setListOpenOnPath(pathname)}
              aria-expanded={listOpen}
              aria-controls="chat-list"
              className="btn-ghost lg:hidden"
            >
              Chats
            </button>
            <h1 className="text-2xl font-bold">Chat</h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {pickersLocked ? (
              !unavailable && (
                <span
                  title="Start a new chat to change"
                  className="rounded-full bg-surface-4 px-3 py-1.5 text-xs text-soft"
                >
                  {lockedModel === undefined
                    ? 'Loading…'
                    : `${lockedCollection ?? 'Agent chooses'} · ${lockedModel}`}
                </span>
              )
            ) : (
              <>
                <select
                  aria-label="Collection"
                  value={collectionName ?? AGENT_CHOOSES_COLLECTION}
                  onChange={(e) => setCollectionOverride(e.target.value)}
                  disabled={collectionsQuery.isLoading}
                  className="field w-auto"
                >
                  <option value={AGENT_CHOOSES_COLLECTION}>Let the agent choose</option>
                  {collections?.map((c) => (
                    <option key={c.name} value={c.name}>
                      {c.name}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="Chat model"
                  value={chatModel}
                  onChange={(e) => setChatModelOverride(e.target.value)}
                  disabled={chatModelsLoading || !chatModels?.length}
                  className="field w-auto"
                >
                  {chatModelsLoading ? (
                    <option value="">Loading models…</option>
                  ) : !chatModels?.length ? (
                    <option value="">No models</option>
                  ) : (
                    chatModels.map((m) => (
                      <option key={m.name} value={m.name}>
                        {m.name}
                      </option>
                    ))
                  )}
                </select>
              </>
            )}
            {/* lg+ has New chat in the always-visible list. */}
            <button type="button" onClick={startNewChat} className="btn-ghost lg:hidden">
              New chat
            </button>
          </div>
        </header>

        <div
          role="log"
          aria-live="polite"
          // Announce the finished answer once, not every streamed token.
          aria-busy={isStreaming}
          aria-label="Conversation"
          className="flex-1 overflow-y-auto px-6 py-6"
        >
          {renderBody()}
        </div>

        {/* A forbidden/missing chat offers only New chat, no input. */}
        {!unavailable && (
          <ChatInput
            key={draft.key}
            initialValue={draft.text}
            failedTurn={chat.failedTurn}
            onSend={chat.send}
            disabled={isThinking || !canSend}
          />
        )}
      </div>
    </div>
  )
}
