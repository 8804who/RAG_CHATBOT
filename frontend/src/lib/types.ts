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

// Single-collection detail (GET /collections/{name}). Qdrant cannot change a
// vector's size/distance after creation, so only on_disk / optimizer params are
// editable — see UpdateCollectionRequest below.
export interface DenseVectorDetail {
  size: number
  distance: string
  on_disk: boolean
}

export interface SparseVectorDetail {
  modifier: string | null
  on_disk: boolean
}

export interface CollectionDetail {
  name: string
  status: string
  points_count: number
  dense_vectors: Record<string, DenseVectorDetail>
  sparse_vectors: Record<string, SparseVectorDetail>
  indexing_threshold: number | null
  default_segment_number: number | null
}

export interface DenseVectorUpdateConfig {
  on_disk?: boolean | null
}

export interface SparseVectorUpdateConfig {
  on_disk?: boolean | null
}

export interface OptimizersConfigUpdate {
  indexing_threshold?: number | null
  default_segment_number?: number | null
}

export interface UpdateCollectionRequest {
  dense_vectors?: Record<string, DenseVectorUpdateConfig>
  sparse_vectors?: Record<string, SparseVectorUpdateConfig>
  optimizers_config?: OptimizersConfigUpdate
}
