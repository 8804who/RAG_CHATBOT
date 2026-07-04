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
class DenseEmbedResult:
    """
    dense 임베딩 batch 결과 + 토큰 사용량

    tokens 는 원격 provider(OpenAI 등)가 보고한 소비 토큰 수. 로컬 모델
    (fastembed)은 API 토큰 개념이 없으므로 None.
    """

    vectors: list[list[float]]
    tokens: int | None = None


@dataclass(slots=True)
class RegisteredEmbeddingModel:
    """
    임베딩 모델 메타 데이터
    """

    name: str
    provider: str
    dimension: int
