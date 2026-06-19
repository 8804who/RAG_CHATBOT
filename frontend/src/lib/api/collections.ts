import type {
  CollectionDetail,
  CollectionsResponse,
  CreateCollectionRequest,
  QdrantCollection,
  UpdateCollectionRequest,
} from '../types'
import { apiFetch } from './client'

// Collections hit the real backend (the /collections route exists), so there is
// no mock branch here unlike chat/documents.

export async function listCollections(): Promise<QdrantCollection[]> {
  const res = await apiFetch<CollectionsResponse>('/api/v1/collections')
  return res.collections
}

export async function getCollection(name: string): Promise<CollectionDetail> {
  return apiFetch<CollectionDetail>(
    `/api/v1/collections/${encodeURIComponent(name)}`,
  )
}

export async function createCollection(
  request: CreateCollectionRequest,
): Promise<boolean> {
  return apiFetch<boolean>('/api/v1/collections', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function updateCollection(
  name: string,
  request: UpdateCollectionRequest,
): Promise<boolean> {
  return apiFetch<boolean>(`/api/v1/collections/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    body: JSON.stringify(request),
  })
}

export async function deleteCollection(name: string): Promise<boolean> {
  return apiFetch<boolean>(`/api/v1/collections/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
}
