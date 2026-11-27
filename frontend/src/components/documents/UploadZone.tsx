import { useRef, useState, type DragEvent } from 'react'

import { MAX_UPLOAD_BYTES, UPLOAD_EXTENSIONS } from '../../lib/config'
import { formatBytes } from '../../lib/format'

interface UploadZoneProps {
  onUpload: (files: File[]) => void
  busy?: boolean
}

export function UploadZone({ onUpload, busy }: UploadZoneProps): React.JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function handleDrop(e: DragEvent<HTMLDivElement>): void {
    e.preventDefault()
    setDragging(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length) onUpload(files)
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center transition ${
        dragging
          ? 'border-primary bg-surface-2'
          : 'border-line-strong bg-surface hover:border-muted'
      }`}
    >
      <span className="mb-2 text-3xl" aria-hidden>
        📥
      </span>
      <p className="text-sm font-bold">Drag &amp; drop documents here</p>
      <p className="mt-0.5 text-xs text-muted">
        Markdown or plain text ({UPLOAD_EXTENSIONS.join(', ')}), up to{' '}
        {formatBytes(MAX_UPLOAD_BYTES)} each
      </p>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={busy}
        className="btn-primary mt-4"
      >
        {busy ? 'Uploading…' : 'Browse files'}
      </button>
      <input
        ref={inputRef}
        type="file"
        multiple
        className="hidden"
        accept={UPLOAD_EXTENSIONS.join(',')}
        onChange={(e) => {
          const files = Array.from(e.target.files ?? [])
          if (files.length) onUpload(files)
          e.target.value = ''
        }}
      />
    </div>
  )
}
