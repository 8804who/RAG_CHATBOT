import type { CollectionDetail } from '../../lib/types'

interface CollectionInfoPanelProps {
  detail: CollectionDetail | undefined
  isLoading: boolean
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-surface-2 px-3 py-2.5">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-0.5 truncate text-sm font-bold">{value}</p>
    </div>
  )
}

export default function CollectionInfoPanel({
  detail,
  isLoading,
}: CollectionInfoPanelProps) {
  if (isLoading || !detail) {
    return (
      <div className="rounded-lg bg-surface p-6">
        <p className="text-center text-sm text-muted">
          {isLoading ? 'Loading collection…' : 'Select a collection.'}
        </p>
      </div>
    )
  }

  const denseNames = Object.keys(detail.dense_vectors)
  const dense = denseNames.length ? detail.dense_vectors[denseNames[0]] : null
  const sparseNames = Object.keys(detail.sparse_vectors)

  return (
    <div className="space-y-4 rounded-lg bg-surface p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-bold">{detail.name}</h2>
        <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-bold text-primary">
          {detail.status}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat label="Points" value={detail.points_count.toLocaleString()} />
        <Stat
          label="Embedding model"
          value={detail.embedding_model ?? '—'}
        />
        <Stat
          label="Dense"
          value={dense ? `${dense.size}d · ${dense.distance}` : '—'}
        />
        <Stat
          label="Sparse"
          value={sparseNames.length ? sparseNames.join(', ') : 'none'}
        />
        <Stat
          label="Indexing threshold"
          value={
            detail.indexing_threshold !== null
              ? String(detail.indexing_threshold)
              : '—'
          }
        />
        <Stat
          label="Segments"
          value={
            detail.default_segment_number !== null
              ? String(detail.default_segment_number)
              : '—'
          }
        />
      </div>
    </div>
  )
}
