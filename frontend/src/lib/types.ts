export interface User {
  id: number
  email: string
  name: string | null
  picture: string | null
}

export type DocumentStatus = 'processing' | 'ready' | 'failed'

export interface RagDocument {
  id: string
  name: string
  sizeBytes: number
  status: DocumentStatus
  chunkCount: number
  createdAt: string
}

export interface Citation {
  documentId: string
  documentName: string
  snippet: string
}

export type MessageRole = 'user' | 'assistant'

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  citations?: Citation[]
  createdAt: string
}

// Vector collections (Qdrant). Field names use snake_case to match the backend
// CreateQdrantCollectionRequest wire format.
export type VectorDistance = 'Cosine' | 'Dot' | 'Euclid' | 'Manhattan'
export type SparseModifier = 'idf' | 'none'

export interface QdrantCollection {
  name: string
}

export interface CollectionsResponse {
  collections: QdrantCollection[]
}

export interface DenseVectorConfig {
  size: number
  distance: VectorDistance
  on_disk: boolean
}

export interface SparseVectorConfig {
  modifier: SparseModifier
  on_disk: boolean
}

export interface EmbeddingModelInfo {
  name: string
  dimension: number
  revision?: string | null
  normalize: boolean
}

export interface CreateCollectionRequest {
  collection_name: string
  dense_vectors: Record<string, DenseVectorConfig>
  sparse_vectors: Record<string, SparseVectorConfig>
  embedding_model: EmbeddingModelInfo
  on_disk_payload: boolean
}
