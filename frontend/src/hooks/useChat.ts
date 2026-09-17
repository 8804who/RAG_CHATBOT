import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'

import { createChat, sendMessage } from '../lib/api/chat'
import type { ChatMessage } from '../lib/types'

const uid = () => Math.random().toString(36).slice(2, 10)

interface UseChatOptions {
  // null/omitted means "let the agent choose the collection per query".
  collectionName: string | null
  chatModel: string | null
}

export function useChat({ collectionName, chatModel }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  // null until the first message is sent, then pinned for the session.
  const [chatId, setChatId] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async (text: string) => {
      let id = chatId
      if (!id) {
        if (!chatModel) {
          throw new Error('Pick a chat model first')
        }
        const chat = await createChat({
          collection_name: collectionName ?? undefined,
          chat_model: chatModel,
        })
        id = chat.id
        setChatId(id)
      }
      return sendMessage(id, text)
    },
    onSuccess: (assistantMessage) => {
      setMessages((prev) => [...prev, assistantMessage])
    },
  })

  function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || mutation.isPending) return
    const userMessage: ChatMessage = {
      id: uid(),
      role: 'user',
      content: trimmed,
      createdAt: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMessage])
    mutation.mutate(trimmed)
  }

  function reset() {
    setMessages([])
    setChatId(null)
    mutation.reset()
  }

  return {
    messages,
    send,
    reset,
    chatId,
    isThinking: mutation.isPending,
    error: mutation.error,
  }
}
