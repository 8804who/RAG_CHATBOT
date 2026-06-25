from dataclasses import dataclass


@dataclass(slots=True)
class SparseVector:
    """
    Sparse 임베딩 결과
    """

    indices: list[int]
    values: list[float]


@dataclass(slots=True)
class EmbeddingResult:
    """
    단일 텍스트 임베딩 결과
    """

    dense: list[float]
    sparse: SparseVector | None = None


@dataclass(slots=True)
class RegisteredEmbeddingModel:
    """
    임베딩 모델 메타 데이터
    """

    name: str
    provider: str
    dimension: int
