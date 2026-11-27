import { CollectionListItem } from '../components/collections/CollectionListItem'
import { CreateCollectionForm } from '../components/collections/CreateCollectionForm'
import { useCollections, useCreateCollection } from '../hooks/useCollections'
import { ApiError } from '../lib/api/client'
import type { CreateCollectionRequest } from '../lib/types'

function createErrorMessage(error: unknown): string | null {
  if (!error) return null
  if (error instanceof ApiError) {
    if (error.status === 409) return 'A collection with that name already exists.'
    if (error.status === 422) return 'Invalid collection settings. Check the dimension.'
    return `Could not create collection (${error.message}).`
  }
  return 'Could not create collection.'
}

export function CollectionsPage(): React.JSX.Element {
  const { data: collections, isLoading, isError } = useCollections()
  const create = useCreateCollection()

  function handleCreate(request: CreateCollectionRequest): void {
    create.mutate(request)
  }

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-surface-2 px-6 py-4">
        <h1 className="text-2xl font-bold">Collections</h1>
        <p className="text-sm text-muted">
          Manage the Qdrant vector collections that back retrieval.
        </p>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <CreateCollectionForm
            onSubmit={handleCreate}
            busy={create.isPending}
            error={createErrorMessage(create.error)}
          />

          <div className="overflow-hidden rounded-lg bg-surface">
            <div className="flex items-center justify-between border-b border-canvas px-5 py-3">
              <h2 className="text-base font-bold">
                Existing collections
              </h2>
              {collections && (
                <span className="text-xs text-muted">
                  {collections.length}{' '}
                  {collections.length === 1 ? 'collection' : 'collections'}
                </span>
              )}
            </div>

            {isLoading ? (
              <p className="px-5 py-8 text-center text-sm text-muted">
                Loading collections…
              </p>
            ) : isError ? (
              <p className="px-5 py-8 text-center text-sm text-negative">
                Could not load collections.
              </p>
            ) : !collections || collections.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-muted">
                No collections yet. Create one above to get started.
              </p>
            ) : (
              <ul className="divide-y divide-canvas">
                {collections.map((collection) => (
                  <CollectionListItem
                    key={collection.name}
                    collection={collection}
                  />
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
