import {
  type UseMutationResult,
  type UseQueryResult,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  chatMessageId,
  createChat,
  deleteChat,
  getChatHistory,
  listChats,
  streamMessage,
} from '../lib/api/chat'
import { ApiError } from '../lib/api/client'
import { uid } from '../lib/id'
import type { ChatHistory, ChatMessage, ChatSummary } from '../lib/types'

function chatKey(chatId: string): string[] {
  return ['chats', chatId, 'messages']
}

// Never a prefix of chatKey (chat ids are UUIDs), so invalidating a chat's
// messages leaves the list alone and vice versa.
const CHAT_LIST_KEY = ['chats', 'list']

export function useChatList(): UseQueryResult<ChatSummary[]> {
  return useQuery({ queryKey: CHAT_LIST_KEY, queryFn: listChats })
}

// onActiveDeleted runs before the deleted chat's cache is dropped, in the same
// tick, so the open page never refetches (and 404s) the chat it is leaving.
// The active id is read at success time: navigating elsewhere mid-delete must
// not reset the chat now on screen.
export function useDeleteChat(
  activeChatId: string | null,
  onActiveDeleted: () => void,
): UseMutationResult<void, Error, string> {
  const qc = useQueryClient()
  const activeRef = useRef(activeChatId)
  useEffect(() => {
    activeRef.current = activeChatId
  }, [activeChatId])
  return useMutation({
    mutationFn: deleteChat,
    onSuccess: (_, id) => {
      if (id === activeRef.current) onActiveDeleted()
      qc.removeQueries({ queryKey: chatKey(id), exact: true })
    },
    // A 404 means it is already gone: refresh either way.
    onSettled: () => qc.invalidateQueries({ queryKey: CHAT_LIST_KEY }),
  })
}

interface UseChatOptions {
  // From the URL (/chat/:chatId); null on /chat (a new chat).
  chatId: string | null
  // Used only when the first message creates the chat. null collection means
  // "let the agent choose the collection per query".
  collectionName: string | null
  chatModel: string | null
}

// The user's in-flight or failed question. A failed turn stores nothing on the
// server (D-016), so Retry resends the same text and the bubble stays local.
interface Turn {
  id: string
  // null until createChat succeeds.
  chatId: string | null
  text: string
  // Streamed answer so far; '' until the first token.
  answer: string
  error: Error | null
}

interface UseChatResult {
  history: ChatHistory | undefined
  historyLoading: boolean
  historyError: Error | null
  refetchHistory: () => void
  messages: ChatMessage[]
  // A turn is running (answer pending or streaming): blocks sending.
  isThinking: boolean
  // Tokens have arrived: the answer bubble replaces the thinking indicator.
  isStreaming: boolean
  error: Error | null
  // The failed question, so the input can offer its text again.
  failedTurn: { id: string; text: string } | null
  send: (text: string) => void
  retry: () => void
  reset: () => void
}

export function useChat({
  chatId,
  collectionName,
  chatModel,
}: UseChatOptions): UseChatResult {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const historyQuery = useQuery({
    queryKey: chatKey(chatId ?? ''),
    queryFn: () => getChatHistory(chatId as string),
    enabled: chatId !== null,
    // History only changes through this client's sends, which write the cache.
    // ponytail: a second tab's turns show after reload, not live.
    staleTime: Infinity,
    retry: (count, err) =>
      !(err instanceof ApiError && (err.status === 403 || err.status === 404)) &&
      count < 2,
  })
  const [turn, setTurn] = useState<Turn | null>(null)
  // A turn keeps running after the page unmounts (leaving /chat, or sign-out
  // clearing the cache): it may then only append to a history still cached,
  // never seed a new chat entry or navigate.
  const mountedRef = useRef(false)
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])
  const inflightRef = useRef<{ controller: AbortController; chatId: string | null } | null>(
    null,
  )

  // Only the turn of the chat on screen is shown; a turn left behind by
  // navigating elsewhere still writes its answer into its own chat's cache.
  const visibleTurn = turn && turn.chatId === chatId ? turn : null
  const isThinking = visibleTurn !== null && visibleTurn.error === null
  const isStreaming = isThinking && visibleTurn.answer !== ''

  const history = chatId ? historyQuery.data : undefined
  const messages: ChatMessage[] = [...(history?.messages ?? [])]
  if (visibleTurn) {
    // Same ids the cache write on done will use, so the bubbles keep their
    // nodes (and the scroll position) when the turn lands in history.
    const n = messages.length
    const msgId = (i: number): string =>
      chatId ? chatMessageId(chatId, n + i) : `${visibleTurn.id}-${i}`
    messages.push({
      id: msgId(0),
      role: 'user',
      content: visibleTurn.text,
      createdAt: '',
    })
    if (isStreaming) {
      messages.push({
        id: msgId(1),
        role: 'assistant',
        content: visibleTurn.answer,
        createdAt: '',
      })
    }
  }

  function abortInflight(): void {
    const inflight = inflightRef.current
    if (!inflight) return
    inflight.controller.abort()
    inflightRef.current = null
    // The aborted turn may still finish server-side: refetch that chat on its
    // next visit (not now, the answer isn't stored yet).
    if (inflight.chatId) {
      void qc.invalidateQueries({
        queryKey: chatKey(inflight.chatId),
        refetchType: 'none',
      })
    }
  }

  async function run(next: Turn): Promise<void> {
    abortInflight()
    const controller = new AbortController()
    const inflight = { controller, chatId: next.chatId }
    inflightRef.current = inflight
    setTurn(next)
    let id = next.chatId
    try {
      if (!id) {
        if (!chatModel) throw new Error('Pick a chat model first.')
        const chat = await createChat(
          { collection_name: collectionName ?? undefined, chat_model: chatModel },
          controller.signal,
        )
        if (controller.signal.aborted || !mountedRef.current) return
        id = chat.id
        qc.setQueryData<ChatHistory>(chatKey(id), {
          chatModel: chat.chat_model,
          collectionName: chat.collection_name,
          messages: [],
        })
        const created = id
        inflight.chatId = created
        setTurn((t) => (t?.id === next.id ? { ...t, chatId: created } : t))
        navigate(`/chat/${encodeURIComponent(id)}`, { replace: true })
        void qc.invalidateQueries({ queryKey: CHAT_LIST_KEY })
      }
      const answer = await streamMessage(
        id,
        next.text,
        (delta) =>
          setTurn((t) => (t?.id === next.id ? { ...t, answer: t.answer + delta } : t)),
        controller.signal,
      )
      const target = id
      // Returning undefined skips the write, so a cache cleared by sign-out
      // stays cleared.
      qc.setQueryData<ChatHistory>(chatKey(target), (old) => {
        if (!old) return undefined
        const n = old.messages.length
        const question: ChatMessage = {
          id: chatMessageId(target, n),
          role: 'user',
          content: next.text,
          createdAt: new Date().toISOString(),
        }
        return {
          ...old,
          messages: [...old.messages, question, { ...answer, id: chatMessageId(target, n + 1) }],
        }
      })
      setTurn((t) => (t?.id === next.id ? null : t))
      // New title / order.
      void qc.invalidateQueries({ queryKey: CHAT_LIST_KEY })
    } catch (err) {
      if (controller.signal.aborted) return
      const error = err instanceof Error ? err : new Error(String(err))
      // Nothing was saved (D-016): drop the partial answer, keep the question for Retry.
      setTurn((t) => (t?.id === next.id ? { ...t, answer: '', error } : t))
    } finally {
      if (inflightRef.current === inflight) inflightRef.current = null
    }
  }

  function send(text: string): void {
    const trimmed = text.trim()
    if (!trimmed || isThinking) return
    void run({ id: uid(), chatId, text: trimmed, answer: '', error: null })
  }

  function retry(): void {
    if (!visibleTurn?.error) return
    void run({ ...visibleTurn, error: null })
  }

  function reset(): void {
    abortInflight()
    setTurn(null)
    navigate('/chat')
  }

  return {
    history,
    historyLoading: chatId !== null && historyQuery.isPending,
    historyError: chatId ? historyQuery.error : null,
    refetchHistory: () => void historyQuery.refetch(),
    messages,
    isThinking,
    isStreaming,
    error: visibleTurn?.error ?? null,
    failedTurn: visibleTurn?.error ? { id: visibleTurn.id, text: visibleTurn.text } : null,
    send,
    retry,
    reset,
  }
}
