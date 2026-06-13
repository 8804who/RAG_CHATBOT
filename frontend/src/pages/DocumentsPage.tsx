import StatusBadge from '../components/documents/StatusBadge'
import UploadZone from '../components/documents/UploadZone'
import {
  useDeleteDocument,
  useDocuments,
  useUploadDocument,
} from '../hooks/useDocuments'
import { formatBytes, formatDate } from '../lib/format'

export default function DocumentsPage() {
  const { data: documents, isLoading } = useDocuments()
  const upload = useUploadDocument()
  const remove = useDeleteDocument()

  function handleUpload(files: File[]) {
    files.forEach((file) => upload.mutate(file))
  }

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <h1 className="text-lg font-semibold">Documents</h1>
        <p className="text-sm text-gray-500">
          Your knowledge base — uploaded files are chunked and embedded for
          retrieval.
        </p>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <UploadZone onUpload={handleUpload} busy={upload.isPending} />

          <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white">
            {isLoading ? (
              <p className="px-5 py-8 text-center text-sm text-gray-400">
                Loading documents…
              </p>
            ) : !documents || documents.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-gray-400">
                No documents yet. Upload one to get started.
              </p>
            ) : (
              <ul className="divide-y divide-gray-100">
                {documents.map((doc) => (
                  <li
                    key={doc.id}
                    className="flex items-center gap-4 px-5 py-3.5"
                  >
                    <span className="text-xl">📄</span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-gray-900">
                        {doc.name}
                      </p>
                      <p className="text-xs text-gray-500">
                        {formatBytes(doc.sizeBytes)} ·{' '}
                        {doc.status === 'ready'
                          ? `${doc.chunkCount} chunks`
                          : '—'}{' '}
                        · {formatDate(doc.createdAt)}
                      </p>
                    </div>
                    <StatusBadge status={doc.status} />
                    <button
                      type="button"
                      onClick={() => remove.mutate(doc.id)}
                      className="rounded-lg px-2 py-1 text-sm text-gray-400 transition hover:bg-red-50 hover:text-red-600"
                      aria-label={`Delete ${doc.name}`}
                    >
                      Delete
                    </button>
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
