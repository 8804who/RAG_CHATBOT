import type { APIRequestContext } from '@playwright/test'

import type { ChatMessageApiResponse } from './types'

export async function createChat(
  request: APIRequestContext,
  collectionName: string | null,
  chatModel: string,
): Promise<string> {
  const res = await request.post('/api/v1/chats', {
    data: { collection_name: collectionName, chat_model: chatModel },
  })
  if (!res.ok()) {
    throw new Error(`createChat failed: ${res.status()} ${await res.text()}`)
  }
  const body = (await res.json()) as { id: string }
  return body.id
}

export async function sendMessage(
  request: APIRequestContext,
  chatId: string,
  query: string,
): Promise<{ response: ChatMessageApiResponse; elapsedMs: number }> {
  const startedAt = Date.now()
  const res = await request.post(`/api/v1/chats/${encodeURIComponent(chatId)}/messages`, {
    data: { query },
  })
  const elapsedMs = Date.now() - startedAt
  if (!res.ok()) {
    throw new Error(`sendMessage failed: ${res.status()} ${await res.text()}`)
  }
  const response = (await res.json()) as ChatMessageApiResponse
  return { response, elapsedMs }
}
