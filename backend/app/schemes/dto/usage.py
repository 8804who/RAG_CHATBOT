from dataclasses import dataclass


@dataclass(slots=True)
class EmbeddingUsageRow:
    """
    모델별 임베딩 토큰 사용량 집계 행(비용 계산 전).
    """

    model: str
    total_tokens: int
    document_count: int


@dataclass(slots=True)
class ChatUsageRow:
    """
    모델별 채팅 토큰 사용량 집계 행(비용 계산 전).
    """

    model: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    message_count: int


@dataclass(slots=True)
class ModelPrice:
    """
    모델 단가(100만 토큰당 USD).
    """

    input_price_per_1m: float
    output_price_per_1m: float
    currency: str
