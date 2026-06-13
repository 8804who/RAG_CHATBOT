import type { DocumentStatus } from '../../lib/types'

const styles: Record<DocumentStatus, string> = {
  ready: 'bg-green-50 text-green-700 ring-green-600/20',
  processing: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  failed: 'bg-red-50 text-red-700 ring-red-600/20',
}

const labels: Record<DocumentStatus, string> = {
  ready: 'Ready',
  processing: 'Processing',
  failed: 'Failed',
}

export default function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${styles[status]}`}
    >
      {status === 'processing' && (
        <span className="size-1.5 animate-pulse rounded-full bg-current" />
      )}
      {labels[status]}
    </span>
  )
}
