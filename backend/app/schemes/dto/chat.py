from dataclasses import dataclass, field


@dataclass(slots=True)
class RegisteredChatModel:
    """
    채팅(생성) 모델 메타 데이터
    """

    name: str
    provider: str


@dataclass(slots=True)
class Citation:
    """
    답변 근거로 인용된 출처 정보

    source_type이 "document"면 chunk_id/document_id/collection_name이 채워지고,
    "web"이면 url이 채워진다(둘 다 title/snippet은 공통).
    """

    source_type: str
    title: str
    snippet: str
    document_id: str | None = None
    chunk_id: str | None = None
    collection_name: str | None = None
    url: str | None = None


@dataclass(slots=True)
class ChatTurnResult:
    """
    한 턴(질문 1회)의 최종 결과: 답변 + 인용 목록
    """

    content: str
    citations: list[Citation] = field(default_factory=list)
