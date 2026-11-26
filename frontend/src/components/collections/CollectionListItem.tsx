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
    <li className="px-5 py-3.5 transition hover:bg-surface-2">
      <div className="flex items-center gap-3">
        <span className="grid size-8 place-items-center rounded-md bg-surface-3 text-muted">
          ▤
        </span>
        <span className="flex-1 truncate text-sm font-bold">
          {collection.name}
        </span>

        {confirmingDelete ? (
          <span className="flex items-center gap-2 text-sm">
            <span className="text-muted">Delete?</span>
            <button
              type="button"
              onClick={handleDelete}
              disabled={remove.isPending}
              className="rounded-full bg-negative px-4 py-1.5 text-sm font-bold text-black transition hover:bg-negative/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-fg disabled:opacity-50"
            >
              {remove.isPending ? 'Deleting…' : 'Confirm'}
            </button>
            <button
              type="button"
              onClick={() => setConfirmingDelete(false)}
              disabled={remove.isPending}
              className="btn-secondary"
            >
              Cancel
            </button>
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setEditing((v) => !v)}
              className="btn-secondary"
            >
              {editing ? 'Close' : 'Edit'}
            </button>
            <button
              type="button"
              onClick={() => setConfirmingDelete(true)}
              className="btn-danger"
            >
              Delete
            </button>
          </span>
        )}
      </div>

      {remove.error && (
        <p className="mt-2 text-xs text-negative">
          {mutationErrorMessage(remove.error, 'delete')}
        </p>
      )}

      {editing && (
        <div className="mt-3">
          {detail.isLoading ? (
            <p className="text-sm text-muted">Loading settings…</p>
          ) : detail.isError || !detail.data ? (
            <p className="text-sm text-negative">Could not load settings.</p>
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