import { useState, type FormEvent } from 'react'

import { useEmbeddingModels } from '../../hooks/useModels'
import type {
  CreateCollectionRequest,
  SparseModifier,
  VectorDistance,
} from '../../lib/types'

interface CreateCollectionFormProps {
  onSubmit: (request: CreateCollectionRequest) => void
  busy?: boolean
  error?: string | null
}

const DISTANCES: VectorDistance[] = ['Cosine', 'Dot', 'Euclid', 'Manhattan']
const SPARSE_MODIFIERS: SparseModifier[] = ['idf', 'none']

const fieldClass =
  'w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-100'
const labelClass = 'mb-1 block text-sm font-medium text-gray-700'

export default function CreateCollectionForm({
  onSubmit,
  busy,
  error,
}: CreateCollectionFormProps) {
  const { data: models, isLoading: modelsLoading } = useEmbeddingModels()
  const [name, setName] = useState('')
  // Explicit user choice overrides the default; otherwise fall back to the first
  // registered model. Derived during render so no setState-in-effect is needed.
  const [modelOverride, setModelOverride] = useState('')
  const [distance, setDistance] = useState<VectorDistance>('Cosine')
  const [denseOnDisk, setDenseOnDisk] = useState(false)
  const [enableSparse, setEnableSparse] = useState(true)
  const [modifier, setModifier] = useState<SparseModifier>('idf')
  const [onDiskPayload, setOnDiskPayload] = useState(true)

  const modelName = modelOverride || models?.[0]?.name || ''
  // The embedding dimension is fixed by the chosen model (the backend rejects a
  // dense vector size that differs from the model dimension).
  const selectedModel = models?.find((m) => m.name === modelName)
  const dimension = selectedModel?.dimension ?? 0

  const trimmedName = name.trim()
  const canSubmit = trimmedName.length > 0 && !!selectedModel && !busy

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!canSubmit || !selectedModel) return

    const request: CreateCollectionRequest = {
      collection_name: trimmedName,
      // Dense vector size must equal the embedding dimension (backend validates).
      dense_vectors: {
        dense: { size: dimension, distance, on_disk: denseOnDisk },
      },
      sparse_vectors: enableSparse
        ? { sparse: { modifier, on_disk: false } }
        : {},
      embedding_model: {
        name: selectedModel.name,
        dimension: selectedModel.dimension,
        normalize: true,
      },
      on_disk_payload: onDiskPayload,
    }
    onSubmit(request)
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-5 rounded-2xl border border-gray-200 bg-white p-6"
    >
      <div>
        <h2 className="text-base font-semibold text-gray-900">
          Create collection
        </h2>
        <p className="text-sm text-gray-500">
          Define the vector space for a new Qdrant collection.
        </p>
      </div>

      <div>
        <label htmlFor="collection-name" className={labelClass}>
          Collection name
        </label>
        <input
          id="collection-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="my-knowledge-base"
          className={fieldClass}
        />
      </div>

      <div>
        <label htmlFor="model-name" className={labelClass}>
          Embedding model
        </label>
        <select
          id="model-name"
          value={modelName}
          onChange={(e) => setModelOverride(e.target.value)}
          disabled={modelsLoading || !models || models.length === 0}
          className={fieldClass}
        >
          {modelsLoading ? (
            <option value="">Loading models…</option>
          ) : !models || models.length === 0 ? (
            <option value="">No models available</option>
          ) : (
            models.map((model) => (
              <option key={model.name} value={model.name}>
                {model.name} · {model.provider} · {model.dimension}d
              </option>
            ))
          )}
        </select>
        <p className="mt-1 text-xs text-gray-500">
          The vector dimension ({dimension || '—'}) is fixed by the chosen model
          and pinned to the collection.
        </p>
      </div>

      <div>
        <label htmlFor="distance" className={labelClass}>
          Distance metric
        </label>
        <select
          id="distance"
          value={distance}
          onChange={(e) => setDistance(e.target.value as VectorDistance)}
          className={fieldClass}
        >
          {DISTANCES.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-3 rounded-xl bg-gray-50 p-4">
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <input
            type="checkbox"
            checked={enableSparse}
            onChange={(e) => setEnableSparse(e.target.checked)}
            className="size-4 rounded border-gray-300 text-brand-500 focus:ring-brand-400"
          />
          Add sparse vectors (hybrid search)
        </label>
        {enableSparse && (
          <div>
            <label htmlFor="modifier" className={labelClass}>
              Sparse modifier
            </label>
            <select
              id="modifier"
              value={modifier}
              onChange={(e) => setModifier(e.target.value as SparseModifier)}
              className={fieldClass}
            >
              {SPARSE_MODIFIERS.map((m) => (
                <option key={m} value={m}>
                  {m === 'idf' ? 'IDF (BM25-style)' : 'None'}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-x-6 gap-y-2">
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={denseOnDisk}
            onChange={(e) => setDenseOnDisk(e.target.checked)}
            className="size-4 rounded border-gray-300 text-brand-500 focus:ring-brand-400"
          />
          Store dense vectors on disk
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={onDiskPayload}
            onChange={(e) => setOnDiskPayload(e.target.checked)}
            className="size-4 rounded border-gray-300 text-brand-500 focus:ring-brand-400"
          />
          Store payload on disk
        </label>
      </div>

      {error && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={!canSubmit}
        className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-50"
      >
        {busy ? 'Creating…' : 'Create collection'}
      </button>
    </form>
  )
}
