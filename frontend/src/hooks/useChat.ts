import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'

import { sendMessage } from '../lib/api/chat'
import type { ChatMessage } from '../lib/types'

const uid = () => Math.random().toString(36).slice(2, 10)

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])

  const mutation = useMutation({
    mutationFn: sendMessage,
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
    mutation.reset()
  }

  return {
    messages,
    send,
    reset,
    isThinking: mutation.isPending,
    error: mutation.error,
  }
}
