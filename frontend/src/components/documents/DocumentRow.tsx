import { useState } from 'react'

import { useDocumentChunks } from '../../hooks/useDocuments'
import { formatDate } from '../../lib/format'
import type { DocumentSummary } from '../../lib/types'

interface DocumentRowProps {
  collection: string
  document: DocumentSummary
  onDelete: (documentId: string) => void
  deleting?: boolean
}

export default function DocumentRow({
  collection,
  document,
  onDelete,
  deleting,
}: DocumentRowProps) {
  const [expanded, setExpanded] = useState(false)
  const { data: chunks, isLoading } = useDocumentChunks(
    collection,
    expanded ? document.document_id : null,
  )

  return (
    <li className="px-5 py-3.5">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="grid size-6 place-items-center rounded text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
          aria-label={expanded ? 'Collapse' : 'Expand'}
          aria-expanded={expanded}
        >
          {expanded ? '▾' : '▸'}
        </button>
        <span className="text-xl">📄</span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-gray-900">
            {document.filename}
          </p>
          <p className="text-xs text-gray-500">
            {document.chunk_count}{' '}
            {document.chunk_count === 1 ? 'chunk' : 'chunks'}
            {document.created_at ? ` · ${formatDate(document.created_at)}` : ''}
          </p>
        </div>
        <button
          type="button"
          onClick={() => onDelete(document.document_id)}
          disabled={deleting}
          className="rounded-lg px-2 py-1 text-sm text-gray-400 transition hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
          aria-label={`Delete ${document.filename}`}
        >
          Delete
        </button>
      </div>

      {expanded && (
        <div className="mt-3 space-y-2 pl-10">
          {isLoading ? (
            <p className="text-xs text-gray-400">Loading chunks…</p>
          ) : !chunks || chunks.length === 0 ? (
            <p className="text-xs text-gray-400">No chunks found.</p>
          ) : (
            chunks.map((chunk) => (
              <div
                key={chunk.chunk_id}
                className="rounded-lg bg-gray-50 px-3 py-2"
              >
                <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-gray-400">
                  Chunk #{chunk.chunk_index}
                </p>
                <p className="line-clamp-4 whitespace-pre-wrap text-xs text-gray-600">
                  {chunk.text}
                </p>
              </div>
            ))
          )}
        </div>
      )}
    </li>
  )
}
