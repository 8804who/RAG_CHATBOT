import { useQuery } from '@tanstack/react-query'

import { listChatModels, listEmbeddingModels } from '../lib/api/models'

export function useEmbeddingModels() {
  return useQuery({
    queryKey: ['models', 'embedding'],
    queryFn: listEmbeddingModels,
    staleTime: 5 * 60 * 1000,
  })
}

export function useChatModels() {
  return useQuery({
    queryKey: ['models', 'chat'],
    queryFn: listChatModels,
    staleTime: 5 * 60 * 1000,
  })
}
