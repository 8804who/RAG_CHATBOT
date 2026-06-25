from dataclasses import dataclass, field

from schemes.dto.embedding import SparseVector


@dataclass(slots=True)
class IngestPoint:
    """
    Qdrant 청크 포인트
    """

    id: str
    dense: list[float]
    payload: dict
    dense_vector_name: str
    sparse: SparseVector | None = None
    sparse_vector_name: str | None = None


@dataclass(slots=True)
class RawPoint:
    """scroll로 읽어온 원시 포인트(id + payload)."""

    id: str
    payload: dict = field(default_factory=dict)


@dataclass(slots=True)
class DocumentSummary:
    """
    컬렉션 내 문서 정보 요약
    """

    document_id: str
    filename: str
    chunk_count: int
    created_at: str | None


@dataclass(slots=True)
class DocumentChunk:
    """
    단일 청크
    """

    chunk_id: str
    chunk_index: int
    text: str
