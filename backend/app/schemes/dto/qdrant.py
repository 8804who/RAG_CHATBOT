from dataclasses import dataclass


@dataclass(slots=True)
class DenseVectorDetail:
    """
    dense vector 구성 정보
    """

    size: int
    distance: str
    on_disk: bool


@dataclass(slots=True)
class SparseVectorDetail:
    """
    sparse vector 구성 정보
    """

    modifier: str | None
    on_disk: bool


@dataclass(slots=True)
class CollectionDetail:
    """
    collection 상세 정보
    """

    name: str
    status: str
    points_count: int
    dense_vectors: dict[str, DenseVectorDetail]
    sparse_vectors: dict[str, SparseVectorDetail]
    indexing_threshold: int | None
    default_segment_number: int | None
    embedding_model: str | None = None


@dataclass(slots=True)
class CollectionSummary:
    """
    collection 목록
    """

    name: str
