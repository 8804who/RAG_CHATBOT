import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { createCollection, listCollections } from '../lib/api/collections'
import type { CreateCollectionRequest } from '../lib/types'

const COLLECTIONS_KEY = ['collections']

export function useCollections() {
  return useQuery({
    queryKey: COLLECTIONS_KEY,
    queryFn: listCollections,
  })
}

export function useCreateCollection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (request: CreateCollectionRequest) => createCollection(request),
    onSuccess: () => qc.invalidateQueries({ queryKey: COLLECTIONS_KEY }),
  })
}
