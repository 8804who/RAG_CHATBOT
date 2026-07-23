from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, computed_field


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
    # progress_percent/estimated_seconds_remaining 계산용 내부 필드. 응답 본문에는 노출하지 않는다.
    embedding_started_at: datetime | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def progress_percent(self) -> float:
        """진행률(%). 청킹이 끝나 total_chunks가 확정되기 전에는 0."""
        if not self.total_chunks:
            return 0.0
        return round(min(self.indexed_chunks / self.total_chunks, 1.0) * 100, 1)

    @computed_field
    @property
    def estimated_seconds_remaining(self) -> int | None:
        """
        잔여 예상 시간(초).

        embedding_started_at 이후 경과 시간 대비 indexed_chunks로 처리 속도를 구해
        남은 청크 수에 곱해 선형 추정한다. 속도를 아직 알 수 없거나(첫 청크 처리 전)
        이미 종결 상태(INDEXED/FAILED)면 None.
        """
        if self.status in ("INDEXED", "FAILED"):
            return None
        if (
            not self.total_chunks
            or not self.embedding_started_at
            or self.indexed_chunks <= 0
        ):
            return None

        elapsed = (
            datetime.now(timezone.utc) - self.embedding_started_at
        ).total_seconds()
        if elapsed <= 0:
            return None

        remaining_chunks = self.total_chunks - self.indexed_chunks
        if remaining_chunks <= 0:
            return 0

        rate = self.indexed_chunks / elapsed
        return round(remaining_chunks / rate)


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
