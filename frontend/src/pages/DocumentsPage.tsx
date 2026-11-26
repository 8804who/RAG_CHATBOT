import { useState } from 'react'

import CollectionInfoPanel from '../components/documents/CollectionInfoPanel'
import DocumentRow from '../components/documents/DocumentRow'
import DocumentUpload from '../components/documents/DocumentUpload'
import IngestProgress from '../components/documents/IngestProgress'
import { useCollection, useCollections } from '../hooks/useCollections'
import {
  useDeleteDocument,
  useDocuments,
  useDocumentStatus,
  useIngestDocument,
} from '../hooks/useDocuments'
import { ApiError } from '../lib/api/client'

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
      <header className="border-b border-surface-2 px-6 py-4">
        <h1 className="text-2xl font-bold">Documents</h1>
        <p className="text-sm text-muted">
          Upload documents into a collection — they are chunked and embedded with
          the collection&apos;s pinned model for retrieval.
        </p>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <div>
            <label
              htmlFor="collection-select"
              className="mb-1 block text-sm font-bold"
            >
              Collection
            </label>
            <select
              id="collection-select"
              value={selected ?? ''}
              onChange={(e) => setOverride(e.target.value || null)}
              disabled={!hasCollections}
              className="field"
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
                <p className="rounded-lg bg-negative/10 px-3 py-2 text-sm text-negative">
                  {ingestErrorMessage(ingest.error)}
                </p>
              )}

              {ingestStatus && ingestStatus.status !== 'INDEXED' && (
                <IngestProgress status={ingestStatus} />
              )}

              <div className="overflow-hidden rounded-lg bg-surface">
                <div className="flex items-center justify-between border-b border-canvas px-5 py-3">
                  <h2 className="text-base font-bold">
                    Documents in this collection
                  </h2>
                  {documents && (
                    <span className="text-xs text-muted">
                      {documents.length}{' '}
                      {documents.length === 1 ? 'document' : 'documents'}
                    </span>
                  )}
                </div>

                {docsLoading ? (
                  <p className="px-5 py-8 text-center text-sm text-muted">
                    Loading documents…
                  </p>
                ) : !documents || documents.length === 0 ? (
                  <p className="px-5 py-8 text-center text-sm text-muted">
                    No documents yet. Upload one above to get started.
                  </p>
                ) : (
                  <ul className="divide-y divide-canvas">
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
