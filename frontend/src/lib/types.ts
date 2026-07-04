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

// Embedding model catalog (GET /models). Drives the model dropdown shown when
// creating a collection.
export interface EmbeddingModel {
  name: string
  provider: string
  dimension: number
}

export interface AvailableModelsResponse {
  embedding: EmbeddingModel[]
}

// Token usage stats (GET /usage/stats), grouped by model, with cost computed
// from per-model pricing. `cost`/`currency` are null when a model has no pricing
// row. Shown on the My page.
export interface EmbeddingUsageStat {
  model: string
  total_tokens: number
  document_count: number
  cost: number | null
  currency: string | null
}

export interface ChatUsageStat {
  model: string
  input_tokens: number
  output_tokens: number
  reasoning_tokens: number
  total_tokens: number
  message_count: number
  cost: number | null
  currency: string | null
}

export interface UsageStatsResponse {
  embedding: EmbeddingUsageStat[]
  chat: ChatUsageStat[]
  total_cost: number
  currency: string
}

// Document ingestion (POST /collections/{name}/documents). The frontend reads a
// text file's contents and sends them as `content`; chunking/embedding happen
// server-side (asynchronously, via Kafka workers) using the collection's pinned
// embedding model.
export interface IngestDocumentRequest {
  filename: string
  content: string
}

// Async ingest progress (documents table). Upload returns UPLOADED (202) and the
// UI polls GET .../status until INDEXED or FAILED.
export type DocumentIngestStatus =
  | 'UPLOADED'
  | 'PARSING'
  | 'EMBEDDING'
  | 'INDEXED'
  | 'FAILED'

// POST /collections/{name}/documents → 202 Accepted.
export interface UploadAcceptedResponse {
  document_id: string
  status: DocumentIngestStatus
}

// GET /collections/{name}/documents/{id}/status.
export interface DocumentStatusResponse {
  document_id: string
  status: DocumentIngestStatus
  filename: string
  total_chunks: number | null
  indexed_chunks: number
  error: string | null
}

export interface DocumentSummary {
  document_id: string
  filename: string
  chunk_count: number
  created_at: string | null
}

export interface DocumentsResponse {
  documents: DocumentSummary[]
}

export interface DocumentChunk {
  chunk_id: string
  chunk_index: number
  text: string
}

export interface DocumentChunksResponse {
  document_id: string
  chunks: DocumentChunk[]
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
  embedding_model: string | null
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
