import type {
  DocumentChunk,
  DocumentChunksResponse,
  DocumentStatusResponse,
  DocumentSummary,
  DocumentsResponse,
  IngestDocumentRequest,
  UploadAcceptedResponse,
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

// Upload is asynchronous: the backend returns 202 with a document_id and an
// UPLOADED status. Actual parsing/embedding/indexing happen in Kafka workers;
// poll getDocumentStatus to track progress.
export async function ingestDocument(
  collection: string,
  request: IngestDocumentRequest,
): Promise<UploadAcceptedResponse> {
  return apiFetch<UploadAcceptedResponse>(basePath(collection), {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function getDocumentStatus(
  collection: string,
  documentId: string,
): Promise<DocumentStatusResponse> {
  return apiFetch<DocumentStatusResponse>(
    `${basePath(collection)}/${encodeURIComponent(documentId)}/status`,
  )
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
