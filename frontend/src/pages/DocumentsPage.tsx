import { useState } from 'react'

import CollectionInfoPanel from '../components/documents/CollectionInfoPanel'
import DocumentRow from '../components/documents/DocumentRow'
import DocumentUpload from '../components/documents/DocumentUpload'
import { useCollection, useCollections } from '../hooks/useCollections'
import {
  useDeleteDocument,
  useDocuments,
  useDocumentStatus,
  useIngestDocument,
} from '../hooks/useDocuments'
import { ApiError } from '../lib/api/client'
import type { DocumentIngestStatus } from '../lib/types'

const STATUS_LABELS: Record<DocumentIngestStatus, string> = {
  UPLOADED: 'Queued…',
  PARSING: 'Chunking…',
  EMBEDDING: 'Embedding…',
  INDEXED: 'Indexed',
  FAILED: 'Failed',
}

function ingestErrorMessage(error: unknown): string | null {
  if (!error) return null
  if (error instanceof ApiError) {
    if (error.status === 400)
      return 'This collection has no pinned embedding model, or the document was empty.'
    if (error.status === 404) return 'Collection not found.'
    return `Could not embed document (error ${error.status}).`
  }
  return 'Could not embed document.'
}

export default function DocumentsPage() {
  const { data: collections } = useCollections()
  // Explicit user choice overrides the default; otherwise fall back to the first
  // collection. Derived during render so no setState-in-effect is needed.
  const [override, setOverride] = useState<string | null>(null)
  const selected = override ?? collections?.[0]?.name ?? null

  const { data: detail, isLoading: detailLoading } = useCollection(selected)
  const { data: documents, isLoading: docsLoading } = useDocuments(selected)
  const ingest = useIngestDocument(selected)
  const remove = useDeleteDocument(selected)
  // Poll the async ingest progress of the most recently uploaded document.
  const { data: ingestStatus } = useDocumentStatus(
    selected,
    ingest.data?.document_id ?? null,
  )

  function handleIngest(filename: string, content: string): void {
    if (!selected) return
    ingest.mutate({ filename, content })
  }

  const hasCollections = collections && collections.length > 0

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <h1 className="text-lg font-semibold">Documents</h1>
        <p className="text-sm text-gray-500">
          Upload documents into a collection — they are chunked and embedded with
          the collection&apos;s pinned model for retrieval.
        </p>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <div>
            <label
              htmlFor="collection-select"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Collection
            </label>
            <select
              id="collection-select"
              value={selected ?? ''}
              onChange={(e) => setOverride(e.target.value || null)}
              disabled={!hasCollections}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-100 disabled:bg-gray-50"
            >
              {!hasCollections ? (
                <option value="">No collections — create one first</option>
              ) : (
                collections.map((collection) => (
                  <option key={collection.name} value={collection.name}>
                    {collection.name}
                  </option>
                ))
              )}
            </select>
          </div>

          {selected && (
            <>
              <CollectionInfoPanel detail={detail} isLoading={detailLoading} />

              <DocumentUpload
                onIngest={handleIngest}
                busy={ingest.isPending}
                disabled={!selected}
              />

              {ingest.isError && (
                <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
                  {ingestErrorMessage(ingest.error)}
                </p>
              )}

              {ingestStatus && ingestStatus.status !== 'INDEXED' && (
                <p
                  className={`rounded-lg px-3 py-2 text-sm ${
                    ingestStatus.status === 'FAILED'
                      ? 'bg-red-50 text-red-600'
                      : 'bg-brand-50 text-brand-700'
                  }`}
                >
                  {ingestStatus.filename}: {STATUS_LABELS[ingestStatus.status]}
                  {ingestStatus.total_chunks !== null &&
                    ingestStatus.status !== 'FAILED' &&
                    ` (${ingestStatus.indexed_chunks}/${ingestStatus.total_chunks} chunks)`}
                  {ingestStatus.status === 'FAILED' &&
                    ingestStatus.error &&
                    ` — ${ingestStatus.error}`}
                </p>
              )}

              <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white">
                <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3">
                  <h2 className="text-sm font-semibold text-gray-900">
                    Documents in this collection
                  </h2>
                  {documents && (
                    <span className="text-xs text-gray-500">
                      {documents.length}{' '}
                      {documents.length === 1 ? 'document' : 'documents'}
                    </span>
                  )}
                </div>

                {docsLoading ? (
                  <p className="px-5 py-8 text-center text-sm text-gray-400">
                    Loading documents…
                  </p>
                ) : !documents || documents.length === 0 ? (
                  <p className="px-5 py-8 text-center text-sm text-gray-400">
                    No documents yet. Upload one above to get started.
                  </p>
                ) : (
                  <ul className="divide-y divide-gray-100">
                    {documents.map((document) => (
                      <DocumentRow
                        key={document.document_id}
                        collection={selected}
                        document={document}
                        onDelete={(id) => remove.mutate(id)}
                        deleting={remove.isPending}
                      />
                    ))}
                  </ul>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
