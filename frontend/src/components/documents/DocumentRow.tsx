import { useRef, useState } from 'react'
import { flushSync } from 'react-dom'

import { useDeleteDocument, useDocumentChunks } from '../../hooks/useDocuments'
import { formatDate } from '../../lib/format'
import type { DocumentSummary } from '../../lib/types'
import { InlineConfirm } from '../InlineConfirm'

interface DocumentRowProps {
  collection: string
  document: DocumentSummary
}

export function DocumentRow({
  collection,
  document,
}: DocumentRowProps): React.JSX.Element {
  const [expanded, setExpanded] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const deleteButtonRef = useRef<HTMLButtonElement>(null)
  const remove = useDeleteDocument(collection)
  const { data: chunks, isLoading } = useDocumentChunks(
    collection,
    expanded ? document.document_id : null,
  )

  return (
    <li className="px-5 py-3.5 transition hover:bg-surface-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="-mx-2.5 grid size-11 shrink-0 place-items-center rounded-full text-muted transition hover:bg-surface-3 hover:text-fg focus-visible:outline-2 focus-visible:outline-fg"
          aria-label={`${expanded ? 'Collapse' : 'Expand'} ${document.filename}`}
          aria-expanded={expanded}
        >
          {expanded ? '▾' : '▸'}
        </button>
        <span className="text-xl" aria-hidden>
          📄
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-bold">{document.filename}</p>
          <p className="text-xs text-muted">
            {document.chunk_count}{' '}
            {document.chunk_count === 1 ? 'chunk' : 'chunks'}
            {document.created_at ? ` · ${formatDate(document.created_at)}` : ''}
          </p>
        </div>
        {confirmingDelete ? (
          <InlineConfirm
            prompt={`Delete ${document.filename}?`}
            pending={remove.isPending}
            onConfirm={() => remove.mutate(document.document_id)}
            onCancel={() => {
              flushSync(() => setConfirmingDelete(false))
              deleteButtonRef.current?.focus()
            }}
          />
        ) : (
          <button
            ref={deleteButtonRef}
            type="button"
            onClick={() => setConfirmingDelete(true)}
            className="btn-danger"
            aria-label={`Delete ${document.filename}`}
          >
            Delete
          </button>
        )}
      </div>

      {remove.error && (
        <p role="alert" className="mt-2 text-xs text-negative">
          Could not delete {document.filename} ({remove.error.message}). Try again.
        </p>
      )}

      {expanded && (
        <div className="mt-3 space-y-2 pl-10">
          {isLoading ? (
            <p className="text-xs text-muted">Loading chunks…</p>
          ) : !chunks || chunks.length === 0 ? (
            <p className="text-xs text-muted">No chunks found.</p>
          ) : (
            chunks.map((chunk) => (
              <div key={chunk.chunk_id} className="rounded-md bg-canvas px-3 py-2">
                <p className="mb-1 text-2xs font-bold uppercase tracking-wide text-muted">
                  Chunk #{chunk.chunk_index}
                </p>
                <p className="line-clamp-4 whitespace-pre-wrap text-xs text-soft">
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
