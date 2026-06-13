import { USE_MOCKS, delay } from '../config'
import type { RagDocument } from '../types'
import { apiFetch } from './client'
import { addDocument, documents, removeDocument } from './mockStore'

export async function listDocuments(): Promise<RagDocument[]> {
  if (USE_MOCKS) {
    await delay(300)
    return [...documents]
  }
  return apiFetch<RagDocument[]>('/api/v1/documents')
}

export async function uploadDocument(file: File): Promise<RagDocument> {
  if (USE_MOCKS) {
    await delay(600)
    return addDocument(file)
  }
  const form = new FormData()
  form.append('file', file)
  return apiFetch<RagDocument>('/api/v1/documents', {
    method: 'POST',
    body: form,
    headers: {}, // let the browser set the multipart boundary
  })
}

export async function deleteDocument(id: string): Promise<void> {
  if (USE_MOCKS) {
    await delay(300)
    removeDocument(id)
    return
  }
  await apiFetch<void>(`/api/v1/documents/${id}`, { method: 'DELETE' })
}
