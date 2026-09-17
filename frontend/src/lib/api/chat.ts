import type {
  ChatMessage,
  ChatMessageResponse,
  ChatResponse,
  CreateChatRequest,
} from '../types'
import { apiFetch } from './client'

const uid = () => Math.random().toString(36).slice(2, 10)

// The /chats routes exist on the backend, so there is no mock branch (unlike
// the previous placeholder implementation).

/** Start a new chat, pinning a generation model (and optionally a collection) for its lifetime. */
export async function createChat(request: CreateChatRequest): Promise<ChatResponse> {
  return apiFetch<ChatResponse>('/api/v1/chats', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

/** Send a question in an existing chat and get the assistant's answer with citations. */
export async function sendMessage(
  chatId: string,
  query: string,
): Promise<ChatMessage> {
  const res = await apiFetch<ChatMessageResponse>(
    `/api/v1/chats/${encodeURIComponent(chatId)}/messages`,
    {
      method: 'POST',
      body: JSON.stringify({ query }),
    },
  )
  return {
    id: uid(),
    role: res.role,
    content: res.content,
    citations: res.citations.map((c) => ({
      sourceType: c.source_type,
      title: c.title,
      snippet: c.snippet,
      documentId: c.document_id,
      chunkId: c.chunk_id,
      collectionName: c.collection_name,
      url: c.url,
    })),
    createdAt: new Date().toISOString(),
  }
}
