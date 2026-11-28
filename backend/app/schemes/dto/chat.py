from dataclasses import dataclass, field
from datetime import datetime

from models import ChatMessage


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


@dataclass(slots=True)
class ChatStreamEvent:
    """
    스트리밍 턴 이벤트 1건

    token이면 content = 답변 조각, error면 content = 사용자용 오류 문구,
    done이면 result = 영속화까지 끝난 턴 결과.
    """

    event: str
    content: str = ""
    result: ChatTurnResult | None = None


@dataclass(slots=True)
class TurnUsage:
    """
    한 턴의 토큰 사용량 합계(에이전트 호출 + 요약 호출)
    """

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0


@dataclass(slots=True)
class ChatHistory:
    """
    채팅 이력: 고정된 채팅 모델·컬렉션 + 메시지 목록(오래된 순)
    """

    chat_model: str
    collection_name: str | None
    messages: list[ChatMessage] = field(default_factory=list)


@dataclass(slots=True)
class ChatSummary:
    """
    채팅 목록 한 항목: 제목(첫 사용자 질문 미리보기) + 마지막 메시지 시각

    title·last_message_at은 메시지가 없는 채팅이면 None.
    """

    id: str
    title: str | None
    chat_model: str
    collection_name: str | None
    created_at: datetime
    last_message_at: datetime | None
