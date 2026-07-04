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
class UploadAcceptedResponse(BaseModel):
    # 비동기 인제스트 접수 응답(202). 실제 임베딩·적재는 워커가 뒤에서 처리한다.
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    status: str


class DocumentStatusResponse(BaseModel):
    # 문서 인제스트 진행 상태(프론트 폴링용).
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    status: str
    filename: str
    total_chunks: int | None = None
    indexed_chunks: int = 0
    error: str | None = None


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


### Usage stats (My page)
class EmbeddingUsageStat(BaseModel):
    # 모델별 임베딩 사용량 + 비용. cost는 단가 미등록 시 None.
    model: str
    total_tokens: int
    document_count: int
    cost: float | None = None
    currency: str | None = None


class ChatUsageStat(BaseModel):
    # 모델별 채팅 사용량(입력/출력/추론 토큰) + 비용. cost는 단가 미등록 시 None.
    model: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int
    message_count: int
    cost: float | None = None
    currency: str | None = None


class UsageStatsResponse(BaseModel):
    # 모델별로 그룹핑된 토큰 사용량과 토큰×단가 기반 비용 합계.
    embedding: list[EmbeddingUsageStat]
    chat: list[ChatUsageStat]
    total_cost: float
    currency: str = "USD"
