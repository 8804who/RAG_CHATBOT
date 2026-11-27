import { useId, useState, type FormEvent } from 'react'

import { MAX_UPLOAD_BYTES, UPLOAD_EXTENSIONS } from '../../lib/config'
import { formatBytes } from '../../lib/format'
import { UploadZone } from './UploadZone'

interface DocumentUploadProps {
  onIngest: (filename: string, content: string) => void
  busy?: boolean
}

function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => reject(reader.error)
    reader.readAsText(file)
  })
}

/** Reads the file, or returns why it can't be uploaded. */
async function readUploadable(file: File): Promise<{ content: string } | { error: string }> {
  const name = file.name.toLowerCase()
  if (!UPLOAD_EXTENSIONS.some((ext) => name.endsWith(ext))) {
    return { error: `${file.name} is not a ${UPLOAD_EXTENSIONS.join(' / ')} file` }
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return { error: `${file.name} is larger than ${formatBytes(MAX_UPLOAD_BYTES)}` }
  }
  const content = await readFileAsText(file).catch(() => '')
  return content.trim() ? { content } : { error: `${file.name} is empty or unreadable` }
}

export function DocumentUpload({
  onIngest,
  busy,
}: DocumentUploadProps): React.JSX.Element {
  const id = useId()
  const [showPaste, setShowPaste] = useState(false)
  const [pasteTitle, setPasteTitle] = useState('')
  const [pasteText, setPasteText] = useState('')
  const [fileErrors, setFileErrors] = useState<string[]>([])

  async function handleFiles(files: File[]): Promise<void> {
    const errors: string[] = []
    for (const file of files) {
      const result = await readUploadable(file)
      if ('error' in result) errors.push(result.error)
      else onIngest(file.name, result.content)
    }
    setFileErrors(errors)
  }

  function handlePasteSubmit(e: FormEvent<HTMLFormElement>): void {
    e.preventDefault()
    const title = pasteTitle.trim() || 'pasted-text.txt'
    if (!pasteText.trim()) return
    onIngest(title, pasteText)
    setPasteTitle('')
    setPasteText('')
    setShowPaste(false)
  }

  return (
    <div>
      <UploadZone onUpload={(files) => void handleFiles(files)} busy={busy} />

      {fileErrors.length > 0 && (
        <ul
          role="alert"
          className="mt-3 space-y-1 rounded-lg bg-negative/10 px-3 py-2 text-sm text-negative"
        >
          {fileErrors.map((message, i) => (
            // Replaced wholesale on each pick, never reordered.
            <li key={`${i}:${message}`}>{message}</li>
          ))}
        </ul>
      )}

      <div className="mt-3">
        {showPaste ? (
          <form
            onSubmit={handlePasteSubmit}
            className="space-y-3 rounded-lg bg-surface p-4"
          >
            <div>
              <label htmlFor={`${id}-title`} className="mb-1 block text-sm font-bold">
                Title (optional)
              </label>
              <input
                id={`${id}-title`}
                type="text"
                value={pasteTitle}
                onChange={(e) => setPasteTitle(e.target.value)}
                placeholder="release-notes.md"
                className="field"
              />
            </div>
            <div>
              <label htmlFor={`${id}-text`} className="mb-1 block text-sm font-bold">
                Document text
              </label>
              <textarea
                id={`${id}-text`}
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                placeholder="Paste document text to embed…"
                rows={6}
                className="field resize-y"
              />
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={busy || !pasteText.trim()}
                className="btn-primary"
              >
                {busy ? 'Embedding…' : 'Add document'}
              </button>
              <button
                type="button"
                onClick={() => setShowPaste(false)}
                className="btn-ghost"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <button
            type="button"
            onClick={() => setShowPaste(true)}
            className="min-h-11 text-sm font-bold text-muted underline-offset-4 hover:text-fg hover:underline focus-visible:outline-2 focus-visible:outline-fg"
          >
            or paste text instead
          </button>
        )}
      </div>
    </div>
  )
}
