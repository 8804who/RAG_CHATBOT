import type { DocumentStatus } from '../../lib/types'

const styles: Record<DocumentStatus, string> = {
  ready: 'bg-primary/10 text-primary ring-primary/30',
  processing: 'bg-warning/10 text-warning ring-warning/30',
  failed: 'bg-negative/10 text-negative ring-negative/30',
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
