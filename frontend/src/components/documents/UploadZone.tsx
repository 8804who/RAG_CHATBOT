import { useRef, useState, type DragEvent } from 'react'

interface UploadZoneProps {
  onUpload: (files: File[]) => void
  busy?: boolean
}

export default function UploadZone({ onUpload, busy }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function handleDrop(e: DragEvent<HTMLDivElement>) {
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
      className={`flex flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition ${
        dragging
          ? 'border-brand-400 bg-brand-50'
          : 'border-gray-300 bg-white hover:border-gray-400'
      }`}
    >
      <span className="mb-2 text-3xl">📥</span>
      <p className="text-sm font-medium text-gray-700">
        Drag &amp; drop documents here
      </p>
      <p className="mt-0.5 text-xs text-gray-500">PDF, Markdown, Word, or text</p>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={busy}
        className="mt-4 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-50"
      >
        {busy ? 'Uploading…' : 'Browse files'}
      </button>
      <input
        ref={inputRef}
        type="file"
        multiple
        className="hidden"
        accept=".pdf,.md,.markdown,.txt,.doc,.docx"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? [])
          if (files.length) onUpload(files)
          e.target.value = ''
        }}
      />
    </div>
  )
}
