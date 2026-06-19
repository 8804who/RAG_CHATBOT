import { useState } from 'react'

import {
  useCollection,
  useDeleteCollection,
  useUpdateCollection,
} from '../../hooks/useCollections'
import { ApiError } from '../../lib/api/client'
import type { QdrantCollection, UpdateCollectionRequest } from '../../lib/types'
import { EditCollectionForm } from './EditCollectionForm'

interface CollectionListItemProps {
  collection: QdrantCollection
}

function mutationErrorMessage(error: unknown, action: string): string | null {
  if (!error) return null
  if (error instanceof ApiError) {
    if (error.status === 404) return 'This collection no longer exists.'
    return `Could not ${action} collection (error ${error.status}).`
  }
  return `Could not ${action} collection.`
}

export function CollectionListItem({
  collection,
}: CollectionListItemProps): React.JSX.Element {
  const [editing, setEditing] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const detail = useCollection(editing ? collection.name : null)
  const update = useUpdateCollection()
  const remove = useDeleteCollection()

  function handleUpdate(request: UpdateCollectionRequest): void {
    update.mutate(
      { name: collection.name, request },
      { onSuccess: () => setEditing(false) },
    )
  }

  function handleDelete(): void {
    remove.mutate(collection.name, {
      onSuccess: () => setConfirmingDelete(false),
    })
  }

  return (
    <li className="px-5 py-3.5">
      <div className="flex items-center gap-3">
        <span className="grid size-8 place-items-center rounded-lg bg-brand-50 text-brand-600">
          ▤
        </span>
        <span className="flex-1 truncate text-sm font-medium text-gray-900">
          {collection.name}
        </span>

        {confirmingDelete ? (
          <span className="flex items-center gap-2 text-sm">
            <span className="text-gray-500">Delete?</span>
            <button
              type="button"
              onClick={handleDelete}
              disabled={remove.isPending}
              className="rounded-md bg-red-500 px-2.5 py-1 text-xs font-medium text-white transition hover:bg-red-600 disabled:opacity-50"
            >
              {remove.isPending ? 'Deleting…' : 'Confirm'}
            </button>
            <button
              type="button"
              onClick={() => setConfirmingDelete(false)}
              disabled={remove.isPending}
              className="rounded-md border border-gray-300 px-2.5 py-1 text-xs font-medium text-gray-700 transition hover:bg-gray-100 disabled:opacity-50"
            >
              Cancel
            </button>
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setEditing((v) => !v)}
              className="rounded-md border border-gray-300 px-2.5 py-1 text-xs font-medium text-gray-700 transition hover:bg-gray-100"
            >
              {editing ? 'Close' : 'Edit'}
            </button>
            <button
              type="button"
              onClick={() => setConfirmingDelete(true)}
              className="rounded-md border border-red-200 px-2.5 py-1 text-xs font-medium text-red-600 transition hover:bg-red-50"
            >
              Delete
            </button>
          </span>
        )}
      </div>

      {remove.error && (
        <p className="mt-2 text-xs text-red-500">
          {mutationErrorMessage(remove.error, 'delete')}
        </p>
      )}

      {editing && (
        <div className="mt-3">
          {detail.isLoading ? (
            <p className="text-sm text-gray-400">Loading settings…</p>
          ) : detail.isError || !detail.data ? (
            <p className="text-sm text-red-500">Could not load settings.</p>
          ) : (
            <EditCollectionForm
              collection={detail.data}
              onSubmit={handleUpdate}
              onCancel={() => setEditing(false)}
              busy={update.isPending}
              error={mutationErrorMessage(update.error, 'update')}
            />
          )}
        </div>
      )}
    </li>
  )
}