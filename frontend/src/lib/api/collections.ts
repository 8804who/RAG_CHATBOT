import type {
  CollectionsResponse,
  CreateCollectionRequest,
  QdrantCollection,
} from '../types'
import { apiFetch } from './client'

// Collections hit the real backend (the /collections route exists), so there is
// no mock branch here unlike chat/documents.

export async function listCollections(): Promise<QdrantCollection[]> {
  const res = await apiFetch<CollectionsResponse>('/api/v1/collections')
  return res.collections
}

export async function createCollection(
  request: CreateCollectionRequest,
): Promise<boolean> {
  return apiFetch<boolean>('/api/v1/collections', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}
