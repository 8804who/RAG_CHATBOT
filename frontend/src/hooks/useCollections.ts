import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createCollection,
  deleteCollection,
  getCollection,
  listCollections,
  updateCollection,
} from '../lib/api/collections'
import type {
  CreateCollectionRequest,
  UpdateCollectionRequest,
} from '../lib/types'

const COLLECTIONS_KEY = ['collections']

export function useCollections() {
  return useQuery({
    queryKey: COLLECTIONS_KEY,
    queryFn: listCollections,
  })
}

export function useCollection(name: string | null) {
  return useQuery({
    queryKey: [...COLLECTIONS_KEY, name],
    queryFn: () => getCollection(name as string),
    enabled: name !== null,
  })
}

export function useCreateCollection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (request: CreateCollectionRequest) => createCollection(request),
    onSuccess: () => qc.invalidateQueries({ queryKey: COLLECTIONS_KEY }),
  })
}

interface UpdateCollectionVariables {
  name: string
  request: UpdateCollectionRequest
}

export function useUpdateCollection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, request }: UpdateCollectionVariables) =>
      updateCollection(name, request),
    onSuccess: () => qc.invalidateQueries({ queryKey: COLLECTIONS_KEY }),
  })
}

export function useDeleteCollection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => deleteCollection(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: COLLECTIONS_KEY }),
  })
}
