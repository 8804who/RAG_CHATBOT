import { useState, type FormEvent } from 'react'

import UploadZone from './UploadZone'

interface DocumentUploadProps {
  onIngest: (filename: string, content: string) => void
  busy?: boolean
  disabled?: boolean
}

function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => reject(reader.error)
    reader.readAsText(file)
  })
}

export default function DocumentUpload({
  onIngest,
  busy,
  disabled,
}: DocumentUploadProps) {
  const [showPaste, setShowPaste] = useState(false)
  const [pasteTitle, setPasteTitle] = useState('')
  const [pasteText, setPasteText] = useState('')

  async function handleFiles(files: File[]): Promise<void> {
    for (const file of files) {
      const content = await readFileAsText(file)
      if (content.trim()) onIngest(file.name, content)
    }
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
    <div className={disabled ? 'pointer-events-none opacity-50' : undefined}>
      <UploadZone
        onUpload={(files) => void handleFiles(files)}
        busy={busy}
      />

      <div className="mt-3">
        {showPaste ? (
          <form
            onSubmit={handlePasteSubmit}
            className="space-y-3 rounded-lg bg-surface p-4"
          >
            <input
              type="text"
              value={pasteTitle}
              onChange={(e) => setPasteTitle(e.target.value)}
              placeholder="Title (e.g. release-notes.md)"
              className="field"
            />
            <textarea
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder="Paste document text to embed…"
              rows={6}
              className="field resize-y"
            />
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
            className="text-sm font-bold text-muted underline-offset-4 hover:text-fg hover:underline focus-visible:outline-2 focus-visible:outline-fg"
          >
            or paste text instead
          </button>
        )}
      </div>
    </div>
  )
}
