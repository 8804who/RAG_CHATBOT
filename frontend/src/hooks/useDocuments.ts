import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  deleteDocument,
  getDocumentChunks,
  ingestDocument,
  listDocuments,
} from '../lib/api/documents'
import type { IngestDocumentRequest } from '../lib/types'

const DOCUMENTS_KEY = ['documents']

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
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: [...DOCUMENTS_KEY, collection] }),
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
