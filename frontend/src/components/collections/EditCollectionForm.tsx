import { useState, type FormEvent } from 'react'

import type { CollectionDetail, UpdateCollectionRequest } from '../../lib/types'

interface EditCollectionFormProps {
  collection: CollectionDetail
  onSubmit: (request: UpdateCollectionRequest) => void
  onCancel: () => void
  busy?: boolean
  error?: string | null
}

const labelClass = 'mb-1 block text-sm font-medium text-gray-700'
const fieldClass =
  'w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-100'

export function EditCollectionForm({
  collection,
  onSubmit,
  onCancel,
  busy,
  error,
}: EditCollectionFormProps): React.JSX.Element {
  const [denseOnDisk, setDenseOnDisk] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      Object.entries(collection.dense_vectors).map(([n, c]) => [n, c.on_disk]),
    ),
  )
  const [sparseOnDisk, setSparseOnDisk] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      Object.entries(collection.sparse_vectors).map(([n, c]) => [n, c.on_disk]),
    ),
  )
  const [indexingThreshold, setIndexingThreshold] = useState<string>(
    collection.indexing_threshold?.toString() ?? '',
  )

  function setDense(name: string, value: boolean): void {
    setDenseOnDisk((prev) => ({ ...prev, [name]: value }))
  }

  function setSparse(name: string, value: boolean): void {
    setSparseOnDisk((prev) => ({ ...prev, [name]: value }))
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>): void {
    e.preventDefault()
    if (busy) return

    // 변경된 항목만 담아 보낸다(Qdrant는 size/distance 변경 불가).
    const request: UpdateCollectionRequest = {}

    const denseChanges: Record<string, { on_disk: boolean }> = {}
    for (const [name, value] of Object.entries(denseOnDisk)) {
      if (value !== collection.dense_vectors[name]?.on_disk) {
        denseChanges[name] = { on_disk: value }
      }
    }
    if (Object.keys(denseChanges).length > 0) request.dense_vectors = denseChanges

    const sparseChanges: Record<string, { on_disk: boolean }> = {}
    for (const [name, value] of Object.entries(sparseOnDisk)) {
      if (value !== collection.sparse_vectors[name]?.on_disk) {
        sparseChanges[name] = { on_disk: value }
      }
    }
    if (Object.keys(sparseChanges).length > 0)
      request.sparse_vectors = sparseChanges

    const threshold = indexingThreshold.trim()
    const parsed = threshold === '' ? null : Number(threshold)
    if (parsed !== collection.indexing_threshold && parsed !== null) {
      request.optimizers_config = { indexing_threshold: parsed }
    }

    onSubmit(request)
  }

  const hasVectors =
    Object.keys(denseOnDisk).length > 0 || Object.keys(sparseOnDisk).length > 0

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-xl bg-gray-50 p-4"
    >
      <div>
        <h3 className="text-sm font-semibold text-gray-900">
          Edit “{collection.name}”
        </h3>
        <p className="text-xs text-gray-500">
          Vector size and distance can’t be changed after creation. Only storage
          and optimizer settings are editable.
        </p>
      </div>

      {hasVectors && (
        <div className="space-y-2">
          {Object.keys(denseOnDisk).map((name) => (
            <label
              key={`dense-${name}`}
              className="flex items-center gap-2 text-sm text-gray-700"
            >
              <input
                type="checkbox"
                checked={denseOnDisk[name]}
                onChange={(e) => setDense(name, e.target.checked)}
                className="size-4 rounded border-gray-300 text-brand-500 focus:ring-brand-400"
              />
              Dense “{name}” stored on disk
            </label>
          ))}
          {Object.keys(sparseOnDisk).map((name) => (
            <label
              key={`sparse-${name}`}
              className="flex items-center gap-2 text-sm text-gray-700"
            >
              <input
                type="checkbox"
                checked={sparseOnDisk[name]}
                onChange={(e) => setSparse(name, e.target.checked)}
                className="size-4 rounded border-gray-300 text-brand-500 focus:ring-brand-400"
              />
              Sparse “{name}” stored on disk
            </label>
          ))}
        </div>
      )}

      <div>
        <label htmlFor="indexing-threshold" className={labelClass}>
          Indexing threshold
        </label>
        <input
          id="indexing-threshold"
          type="number"
          min={0}
          value={indexingThreshold}
          onChange={(e) => setIndexingThreshold(e.target.value)}
          placeholder="e.g. 20000"
          className={fieldClass}
        />
      </div>

      {error && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
          {error}
        </p>
      )}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-50"
        >
          {busy ? 'Saving…' : 'Save changes'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100 disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}