import type { AvailableModelsResponse, ChatModel, EmbeddingModel } from '../types'
import { apiFetch } from './client'

// The /models route exists on the backend, so there is no mock branch.

export async function listEmbeddingModels(): Promise<EmbeddingModel[]> {
  const res = await apiFetch<AvailableModelsResponse>('/api/v1/models')
  return res.embedding
}

export async function listChatModels(): Promise<ChatModel[]> {
  const res = await apiFetch<AvailableModelsResponse>('/api/v1/models')
  return res.chat
}
