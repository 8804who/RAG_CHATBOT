import { uid } from '../id'
import type {
  ChatHistory,
  ChatHistoryResponse,
  ChatListResponse,
  ChatMessage,
  ChatMessageResponse,
  ChatResponse,
  Citation,
  CitationResponse,
  ChatSummary,
  CreateChatRequest,
  StreamErrorEvent,
  StreamTokenEvent,
} from '../types'
import { ApiError, apiFetch, apiResponse } from './client'
import { readSse } from './sse'

function toCitation(c: CitationResponse): Citation {
  return {
    sourceType: c.source_type,
    title: c.title,
    snippet: c.snippet,
    documentId: c.document_id,
    chunkId: c.chunk_id,
    collectionName: c.collection_name,
    url: c.url,
  }
}

/**
 * Stable key for the message at `index` of a chat. History is append-only and
 * oldest first, so a refetch keeps every key (no remount, no scroll jump).
 */
export function chatMessageId(chatId: string, index: number): string {
  return `${chatId}-${index}`
}

function chatPath(chatId: string): string {
  return `/api/v1/chats/${encodeURIComponent(chatId)}/messages`
}

/** Start a new chat, pinning a generation model (and optionally a collection) for its lifetime. */
export async function createChat(
  request: CreateChatRequest,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  return apiFetch<ChatResponse>('/api/v1/chats', {
    method: 'POST',
    body: JSON.stringify(request),
    signal,
  })
}

function toAnswer(res: ChatMessageResponse): ChatMessage {
  return {
    id: uid(),
    role: res.role,
    content: res.content,
    citations: res.citations.map(toCitation),
    createdAt: new Date().toISOString(),
  }
}

/**
 * Send a question and stream the answer: `onToken` gets each text delta, then
 * the promise resolves with the final answer (authoritative over the deltas).
 * A stream `error` event, or a stream ending without `done`, rejects with ApiError.
 */
export async function streamMessage(
  chatId: string,
  query: string,
  onToken: (delta: string) => void,
  signal?: AbortSignal,
): Promise<ChatMessage> {
  const res = await apiResponse(`${chatPath(chatId)}/stream`, {
    method: 'POST',
    body: JSON.stringify({ query }),
    signal,
  })
  if (res.body) {
    for await (const { event, data } of readSse(res.body)) {
      if (event === 'token') onToken((JSON.parse(data) as StreamTokenEvent).content)
      else if (event === 'done') return toAnswer(JSON.parse(data) as ChatMessageResponse)
      else if (event === 'error') {
        throw new ApiError(res.status, (JSON.parse(data) as StreamErrorEvent).detail)
      }
    }
  }
  throw new ApiError(res.status, 'The answer stream ended before the answer was complete.')
}

/** Load a chat's pinned model/collection and stored messages (oldest first). */
export async function getChatHistory(chatId: string): Promise<ChatHistory> {
  const res = await apiFetch<ChatHistoryResponse>(chatPath(chatId))
  return {
    chatModel: res.chat_model,
    collectionName: res.collection_name,
    messages: res.messages.map((m, i) => ({
      id: chatMessageId(chatId, i),
      role: m.role,
      content: m.content,
      citations: m.citations.map(toCitation),
      createdAt: m.created_at,
    })),
  }
}

/** List the user's chats, newest activity first. */
export async function listChats(): Promise<ChatSummary[]> {
  const res = await apiFetch<ChatListResponse>('/api/v1/chats')
  return res.chats.map((c) => ({
    id: c.id,
    title: c.title,
    chatModel: c.chat_model,
    collectionName: c.collection_name,
    createdAt: c.created_at,
    lastMessageAt: c.last_message_at,
  }))
}

/** Delete a chat and its messages (409 while one of its turns is running). */
export async function deleteChat(chatId: string): Promise<void> {
  await apiFetch<void>(`/api/v1/chats/${encodeURIComponent(chatId)}`, {
    method: 'DELETE',
  })
}
