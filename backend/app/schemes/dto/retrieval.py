from dataclasses import dataclass, field


@dataclass(slots=True)
class RetrievedPoint:
    """
    Qdrant 검색 결과 원본 포인트(레포지토리 레이어 반환 타입)
    """

    id: str
    score: float
    payload: dict = field(default_factory=dict)


@dataclass(slots=True)
class RetrievedChunk:
    """
    검색된 청크(서비스 레이어가 반환하는 타입)

    RetrievedPoint의 payload를 해석해 상위 레이어(생성/인용)가 dict를 직접
    다루지 않도록 타입으로 감싼다.
    """

    chunk_id: str
    document_id: str
    filename: str
    chunk_index: int
    text: str
    score: float
