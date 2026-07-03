from typing import Self

from pydantic import BaseModel


class _KafkaEvent(BaseModel):
    """Kafka 메시지 직렬화 공통 헬퍼(JSON bytes ↔ 이벤트)."""

    def to_bytes(self) -> bytes:
        """이벤트를 JSON bytes로 직렬화(메시지 value)."""
        return self.model_dump_json().encode()

    @classmethod
    def from_bytes(cls, raw: bytes) -> Self:
        """메시지 value(JSON bytes)를 이벤트로 역직렬화."""
        return cls.model_validate_json(raw)


class DocumentUploadedEvent(_KafkaEvent):
    """documents.uploaded 페이로드. 업로드 원문을 담아 Parser Worker로 전달."""

    document_id: str
    collection_name: str
    filename: str
    content: str
    requester_id: int | None = None
    requester_email: str | None = None


class DocumentParsedEvent(_KafkaEvent):
    """documents.parsed 페이로드(청크당 1메시지). Embed Worker로 전달."""

    document_id: str
    collection_name: str
    filename: str
    chunk_id: str
    chunk_index: int
    text: str
    total_chunks: int
    embedding_model: str
    dense_vector_name: str
    sparse_vector_name: str | None = None
    with_sparse: bool = False
    requester_id: int | None = None
    requester_email: str | None = None


class ChunkEmbeddedEvent(_KafkaEvent):
    """chunks.embed 페이로드(임베딩 결과). Index Worker로 전달."""

    document_id: str
    collection_name: str
    filename: str
    chunk_id: str
    chunk_index: int
    text: str
    total_chunks: int
    created_at: str
    dense: list[float]
    dense_vector_name: str
    sparse_indices: list[int] | None = None
    sparse_values: list[float] | None = None
    sparse_vector_name: str | None = None
    requester_id: int | None = None
    requester_email: str | None = None


class DlqEvent(_KafkaEvent):
    """documents.dlq 페이로드. 실패한 원본 메시지와 실패 맥락을 격리 보관."""

    stage: str
    error: str
    retry_count: int
    source_topic: str
    key: str | None = None
    original: str
