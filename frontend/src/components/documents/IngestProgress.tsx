import { useDocumentStatus, type UploadItem } from '../../hooks/useDocuments'
import { ApiError } from '../../lib/api/client'
import { formatSecondsRemaining } from '../../lib/format'
import type { DocumentIngestStatus } from '../../lib/types'

interface IngestProgressProps {
  collection: string
  upload: UploadItem
}

const STATUS_LABELS: Record<DocumentIngestStatus, string> = {
  UPLOADED: 'Queued…',
  PARSING: 'Chunking…',
  EMBEDDING: 'Embedding…',
  INDEXED: 'Indexed',
  FAILED: 'Failed',
}

// Tailwind can't resolve a class built from a runtime number (`w-[${percent}%]`
// isn't statically analyzable), so the bar snaps to a fixed 5% step and picks
// from this literal table instead of using an inline style.
const WIDTH_CLASSES = [
  'w-[0%]',
  'w-[5%]',
  'w-[10%]',
  'w-[15%]',
  'w-[20%]',
  'w-[25%]',
  'w-[30%]',
  'w-[35%]',
  'w-[40%]',
  'w-[45%]',
  'w-[50%]',
  'w-[55%]',
  'w-[60%]',
  'w-[65%]',
  'w-[70%]',
  'w-[75%]',
  'w-[80%]',
  'w-[85%]',
  'w-[90%]',
  'w-[95%]',
  'w-[100%]',
]

function clampPercent(percent: number): number {
  return Math.max(0, Math.min(100, Math.round(percent)))
}

function widthClassFor(percent: number): string {
  return WIDTH_CLASSES[Math.round(clampPercent(percent) / 5)]
}

function uploadErrorMessage(error: Error): string {
  if (error instanceof ApiError) {
    if (error.status === 400)
      return 'This collection has no pinned embedding model, or the document was empty.'
    if (error.status === 404) return 'Collection not found. Pick another collection.'
  }
  return `Upload failed (${error.message}). Try again.`
}

export function IngestProgress({
  collection,
  upload,
}: IngestProgressProps): React.JSX.Element {
  const {
    data: status,
    isError: pollFailed,
    isFetching: pollRetrying,
    refetch,
  } = useDocumentStatus(
    collection,
    upload.documentId,
  )

  const failed = upload.error !== null || pollFailed || status?.status === 'FAILED'
  const label = upload.error
    ? uploadErrorMessage(upload.error)
    : pollFailed
      ? 'Could not check progress. Retry, or check the document list below.'
      : status
        ? STATUS_LABELS[status.status]
        : 'Uploading…'
  const percent = status ? clampPercent(status.progress_percent) : 0

  return (
    <li
      role="status"
      className={`rounded-lg px-3 py-2 text-sm ${
        failed ? 'bg-negative/10 text-negative' : 'bg-surface-2 text-fg'
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="min-w-0 truncate">
          {upload.filename}: {label}
          {status?.total_chunks != null &&
            !failed &&
            ` (${status.indexed_chunks}/${status.total_chunks} chunks)`}
        </span>
        {!failed && status?.estimated_seconds_remaining != null && (
          <span className="shrink-0 text-xs text-muted">
            {formatSecondsRemaining(status.estimated_seconds_remaining)}
          </span>
        )}
      </div>

      {!failed && status?.status !== 'INDEXED' && (
        <div
          role="progressbar"
          aria-label={`${upload.filename} ingest progress`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-4"
        >
          <div
            className={`h-full rounded-full bg-primary transition-[width] ${widthClassFor(percent)}`}
          />
        </div>
      )}

      {pollFailed && (
        <button
          type="button"
          onClick={() => void refetch()}
          disabled={pollRetrying}
          className="btn-secondary mt-2"
        >
          {pollRetrying ? 'Retrying…' : 'Retry'}
        </button>
      )}

      {status?.status === 'FAILED' && status.error && (
        <p className="mt-1 text-xs">{status.error}</p>
      )}
    </li>
  )
}
