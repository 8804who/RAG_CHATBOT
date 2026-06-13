import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  deleteDocument,
  listDocuments,
  uploadDocument,
} from '../lib/api/documents'

const DOCUMENTS_KEY = ['documents']

export function useDocuments() {
  return useQuery({
    queryKey: DOCUMENTS_KEY,
    queryFn: listDocuments,
    // Poll while anything is still processing so the status flips to ready.
    refetchInterval: (query) =>
      query.state.data?.some((d) => d.status === 'processing') ? 1500 : false,
  })
}

export function useUploadDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => uploadDocument(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: DOCUMENTS_KEY }),
  })
}

export function useDeleteDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: DOCUMENTS_KEY }),
  })
}
