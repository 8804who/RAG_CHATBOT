from dataclasses import dataclass


@dataclass(slots=True)
class DenseVectorDetail:
    """dense vector 구성 정보 DTO."""

    size: int
    distance: str
    on_disk: bool


@dataclass(slots=True)
class SparseVectorDetail:
    """sparse vector 구성 정보 DTO."""

    modifier: str | None
    on_disk: bool


@dataclass(slots=True)
class CollectionDetail:
    """collection 단건 상세 정보 DTO."""

    name: str
    status: str
    points_count: int
    dense_vectors: dict[str, DenseVectorDetail]
    sparse_vectors: dict[str, SparseVectorDetail]
    indexing_threshold: int | None
    default_segment_number: int | None
    # collection_meta에 고정된 임베딩 모델(이 흐름으로 생성되지 않은 컬렉션은 None).
    embedding_model: str | None = None


@dataclass(slots=True)
class CollectionSummary:
    """collection 목록 항목 DTO."""

    name: str
