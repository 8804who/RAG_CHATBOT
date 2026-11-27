import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import {
  deleteDocument,
  getDocumentChunks,
  getDocumentStatus,
  ingestDocument,
  listDocuments,
} from '../lib/api/documents'
import { uid } from '../lib/id'
import type { DocumentIngestStatus, IngestDocumentRequest } from '../lib/types'

const DOCUMENTS_KEY = ['documents']
// Kept outside the documents prefix so invalidating a collection's documents
// never refetches (or loops) the status polls.
const INGEST_STATUS_KEY = ['ingest-status']

// The document list and the collection's detail ("Points" stat) both change
// when a document is uploaded, indexed or deleted.
function invalidateCollectionData(
  qc: ReturnType<typeof useQueryClient>,
  collection: string | null,
): void {
  void qc.invalidateQueries({ queryKey: [...DOCUMENTS_KEY, collection], exact: true })
  void qc.invalidateQueries({ queryKey: ['collections', collection], exact: true })
}

const TERMINAL_STATUSES: DocumentIngestStatus[] = ['INDEXED', 'FAILED']
const STATUS_POLL_MS = 1500

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

/** One upload in this page session. `documentId` is set once the backend accepted it. */
export interface UploadItem {
  id: string
  filename: string
  documentId: string | null
  error: Error | null
}

interface UploadState {
  collection: string | null
  items: UploadItem[]
}

interface IngestVariables {
  collection: string
  request: IngestDocumentRequest
}

/**
 * Tracks every upload separately (one mutateAsync per file), scoped to the
 * selected collection: switching collection hides the previous uploads, so no
 * status poll runs against the wrong collection.
 */
interface DocumentUploads {
  uploads: UploadItem[]
  upload: (filename: string, content: string) => Promise<void>
  uploading: boolean
}

export function useDocumentUploads(collection: string | null): DocumentUploads {
  const qc = useQueryClient()
  const [state, setState] = useState<UploadState>({ collection, items: [] })
  const ingest = useMutation({
    mutationFn: ({ collection: target, request }: IngestVariables) =>
      ingestDocument(target, request),
    onSuccess: (_data, { collection: target }) =>
      invalidateCollectionData(qc, target),
  })

  const uploads = state.collection === collection ? state.items : []

  function patch(target: string, id: string, change: Partial<UploadItem>): void {
    setState((prev) =>
      prev.collection === target
        ? {
            ...prev,
            items: prev.items.map((i) => (i.id === id ? { ...i, ...change } : i)),
          }
        : prev,
    )
  }

  async function upload(filename: string, content: string): Promise<void> {
    if (!collection) return
    const target = collection
    const item: UploadItem = { id: uid(), filename, documentId: null, error: null }
    setState((prev) => ({
      collection: target,
      items: prev.collection === target ? [...prev.items, item] : [item],
    }))
    try {
      const res = await ingest.mutateAsync({
        collection: target,
        request: { filename, content },
      })
      patch(target, item.id, { documentId: res.document_id })
    } catch (error) {
      patch(target, item.id, {
        error: error instanceof Error ? error : new Error(String(error)),
      })
    }
  }

  const uploading = uploads.some((u) => u.documentId === null && u.error === null)
  return { uploads, upload, uploading }
}

// Polls the async ingest status until INDEXED/FAILED (or the poll errors; the
// caller offers Retry via `refetch`, which resumes polling). On INDEXED or a
// poll error the document list and collection stats are refreshed once.
export function useDocumentStatus(
  collection: string | null,
  documentId: string | null,
) {
  const qc = useQueryClient()
  const query = useQuery({
    queryKey: [...INGEST_STATUS_KEY, collection, documentId],
    queryFn: () => getDocumentStatus(collection as string, documentId as string),
    enabled: collection !== null && documentId !== null,
    refetchInterval: (q) =>
      q.state.status === 'error' ||
      (q.state.data && TERMINAL_STATUSES.includes(q.state.data.status))
        ? false
        : STATUS_POLL_MS,
  })

  const settled = query.data?.status === 'INDEXED' || query.isError
  useEffect(() => {
    if (settled) invalidateCollectionData(qc, collection)
  }, [settled, collection, qc])

  return query
}

export function useDeleteDocument(collection: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (documentId: string) => deleteDocument(collection, documentId),
    onSuccess: () => invalidateCollectionData(qc, collection),
  })
}
