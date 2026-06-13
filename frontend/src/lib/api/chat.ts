import { USE_MOCKS, delay } from '../config'
import type { ChatMessage } from '../types'
import { apiFetch } from './client'
import { mockAnswer } from './mockStore'

const uid = () => Math.random().toString(36).slice(2, 10)

/** Send a user question and get the assistant's answer with citations. */
export async function sendMessage(question: string): Promise<ChatMessage> {
  if (USE_MOCKS) {
    await delay(900)
    const { content, citations } = mockAnswer(question)
    return {
      id: uid(),
      role: 'assistant',
      content,
      citations,
      createdAt: new Date().toISOString(),
    }
  }
  return apiFetch<ChatMessage>('/api/v1/chat', {
    method: 'POST',
    body: JSON.stringify({ message: question }),
  })
}
