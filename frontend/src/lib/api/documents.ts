import type {
  DocumentChunk,
  DocumentChunksResponse,
  DocumentSummary,
  DocumentsResponse,
  IngestDocumentRequest,
} from '../types'
import { apiFetch } from './client'

// Documents are scoped to a collection and hit the real backend (the
// /collections/{name}/documents routes exist), so there is no mock branch.

function basePath(collection: string): string {
  return `/api/v1/collections/${encodeURIComponent(collection)}/documents`
}

export async function listDocuments(
  collection: string,
): Promise<DocumentSummary[]> {
  const res = await apiFetch<DocumentsResponse>(basePath(collection))
  return res.documents
}

export async function ingestDocument(
  collection: string,
  request: IngestDocumentRequest,
): Promise<DocumentSummary> {
  return apiFetch<DocumentSummary>(basePath(collection), {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function getDocumentChunks(
  collection: string,
  documentId: string,
): Promise<DocumentChunk[]> {
  const res = await apiFetch<DocumentChunksResponse>(
    `${basePath(collection)}/${encodeURIComponent(documentId)}/chunks`,
  )
  return res.chunks
}

export async function deleteDocument(
  collection: string,
  documentId: string,
): Promise<boolean> {
  return apiFetch<boolean>(
    `${basePath(collection)}/${encodeURIComponent(documentId)}`,
    { method: 'DELETE' },
  )
}
