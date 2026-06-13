import CreateCollectionForm from '../components/collections/CreateCollectionForm'
import { useCollections, useCreateCollection } from '../hooks/useCollections'
import { ApiError } from '../lib/api/client'
import type { CreateCollectionRequest } from '../lib/types'

function createErrorMessage(error: unknown): string | null {
  if (!error) return null
  if (error instanceof ApiError) {
    if (error.status === 409) return 'A collection with that name already exists.'
    if (error.status === 422) return 'Invalid collection settings. Check the dimension.'
    return `Could not create collection (error ${error.status}).`
  }
  return 'Could not create collection.'
}

export default function CollectionsPage() {
  const { data: collections, isLoading, isError } = useCollections()
  const create = useCreateCollection()

  function handleCreate(request: CreateCollectionRequest) {
    create.mutate(request)
  }

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <h1 className="text-lg font-semibold">Collections</h1>
        <p className="text-sm text-gray-500">
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

          <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white">
            <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3">
              <h2 className="text-sm font-semibold text-gray-900">
                Existing collections
              </h2>
              {collections && (
                <span className="text-xs text-gray-500">
                  {collections.length}{' '}
                  {collections.length === 1 ? 'collection' : 'collections'}
                </span>
              )}
            </div>

            {isLoading ? (
              <p className="px-5 py-8 text-center text-sm text-gray-400">
                Loading collections…
              </p>
            ) : isError ? (
              <p className="px-5 py-8 text-center text-sm text-red-500">
                Could not load collections.
              </p>
            ) : !collections || collections.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-gray-400">
                No collections yet. Create one above to get started.
              </p>
            ) : (
              <ul className="divide-y divide-gray-100">
                {collections.map((collection) => (
                  <li
                    key={collection.name}
                    className="flex items-center gap-3 px-5 py-3.5"
                  >
                    <span className="grid size-8 place-items-center rounded-lg bg-brand-50 text-brand-600">
                      ▤
                    </span>
                    <span className="truncate text-sm font-medium text-gray-900">
                      {collection.name}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
