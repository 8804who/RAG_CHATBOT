import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  deleteDocument,
  getDocumentChunks,
  getDocumentStatus,
  ingestDocument,
  listDocuments,
} from '../lib/api/documents'
import type { DocumentIngestStatus, IngestDocumentRequest } from '../lib/types'

const DOCUMENTS_KEY = ['documents']

const TERMINAL_STATUSES: DocumentIngestStatus[] = ['INDEXED', 'FAILED']

export function useDocuments(collection: string | null) {
  return useQuery({
    queryKey: [...DOCUMENTS_KEY, collection],
    queryFn: () => listDocuments(collection as string),
    enabled: collection !== null,
  })
}

export function useDocumentChunks(
  collection: string | null,
  documentId: string | null,
) {
  return useQuery({
    queryKey: [...DOCUMENTS_KEY, collection, documentId, 'chunks'],
    queryFn: () => getDocumentChunks(collection as string, documentId as string),
    enabled: collection !== null && documentId !== null,
  })
}

export function useIngestDocument(collection: string | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (request: IngestDocumentRequest) =>
      ingestDocument(collection as string, request),
    // Upload only enqueues the document (202). The list is refreshed once the
    // status poll (useDocumentStatus) reaches INDEXED.
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: [...DOCUMENTS_KEY, collection] }),
  })
}

// Polls the async ingest status until INDEXED/FAILED. When it reaches INDEXED the
// document list is invalidated so the newly indexed document appears.
export function useDocumentStatus(
  collection: string | null,
  documentId: string | null,
) {
  const qc = useQueryClient()
  return useQuery({
    queryKey: [...DOCUMENTS_KEY, collection, documentId, 'status'],
    queryFn: async () => {
      const status = await getDocumentStatus(
        collection as string,
        documentId as string,
      )
      if (status.status === 'INDEXED') {
        qc.invalidateQueries({ queryKey: [...DOCUMENTS_KEY, collection] })
      }
      return status
    },
    enabled: collection !== null && documentId !== null,
    // Stop polling once the document reaches a terminal state.
    refetchInterval: (query) =>
      query.state.data &&
      TERMINAL_STATUSES.includes(query.state.data.status)
        ? false
        : 1500,
  })
}

export function useDeleteDocument(collection: string | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (documentId: string) =>
      deleteDocument(collection as string, documentId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: [...DOCUMENTS_KEY, collection] }),
  })
}
