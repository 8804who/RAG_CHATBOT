import { formatSecondsRemaining } from '../../lib/format'
import type { DocumentIngestStatus, DocumentStatusResponse } from '../../lib/types'

interface IngestProgressProps {
  status: DocumentStatusResponse
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

function widthClassFor(percent: number): string {
  const step = Math.max(0, Math.min(100, Math.round(percent / 5) * 5))
  return WIDTH_CLASSES[step / 5]
}

export default function IngestProgress({ status }: IngestProgressProps) {
  const isFailed = status.status === 'FAILED'

  return (
    <div
      className={`rounded-lg px-3 py-2 text-sm ${
        isFailed ? 'bg-red-50 text-red-600' : 'bg-brand-50 text-brand-700'
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="truncate">
          {status.filename}: {STATUS_LABELS[status.status]}
          {status.total_chunks !== null &&
            !isFailed &&
            ` (${status.indexed_chunks}/${status.total_chunks} chunks)`}
        </span>
        {status.estimated_seconds_remaining !== null && (
          <span className="shrink-0 text-xs text-brand-600">
            {formatSecondsRemaining(status.estimated_seconds_remaining)}
          </span>
        )}
      </div>

      {!isFailed && (
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-brand-100">
          <div
            className={`h-full rounded-full bg-brand-500 transition-[width] ${widthClassFor(
              status.progress_percent,
            )}`}
          />
        </div>
      )}

      {isFailed && status.error && <p className="mt-1 text-xs">{status.error}</p>}
    </div>
  )
}