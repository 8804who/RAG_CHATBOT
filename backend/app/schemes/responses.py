from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginResponse(BaseModel):
    # Opaque session token; the client sends it as `Authorization: Bearer <token>`.
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str | None
    picture: str | None


### Qdrant
class DenseVectorDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    size: int
    distance: str
    on_disk: bool


class SparseVectorDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    modifier: str | None
    on_disk: bool


class CollectionDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    status: str
    points_count: int
    dense_vectors: dict[str, DenseVectorDetail]
    sparse_vectors: dict[str, SparseVectorDetail]
    indexing_threshold: int | None
    default_segment_number: int | None
    embedding_model: str | None = None


class CollectionSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str


class CollectionsResponse(BaseModel):
    collections: list[CollectionSummaryResponse]


### Models (embedding catalog)
class EmbeddingModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    provider: str
    dimension: int


class AvailableModelsResponse(BaseModel):
    # 프론트 드롭다운 소스. 채팅 모델은 추후 chat 필드로 확장.
    embedding: list[EmbeddingModelResponse]


### Documents (ingestion)
class DocumentSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    filename: str
    chunk_count: int
    created_at: str | None


class DocumentsResponse(BaseModel):
    documents: list[DocumentSummaryResponse]


class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    chunk_index: int
    text: str


class DocumentChunksResponse(BaseModel):
    document_id: str
    chunks: list[DocumentChunkResponse]
