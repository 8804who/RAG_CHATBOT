import { useQuery } from '@tanstack/react-query'

import { listEmbeddingModels } from '../lib/api/models'

export function useEmbeddingModels() {
  return useQuery({
    queryKey: ['models', 'embedding'],
    queryFn: listEmbeddingModels,
    staleTime: 5 * 60 * 1000,
  })
}
