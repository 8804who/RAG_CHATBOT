from dataclasses import dataclass, field


@dataclass(slots=True)
class RegisteredChatModel:
    """
    채팅(생성) 모델 메타 데이터
    """

    name: str
    provider: str


@dataclass(slots=True)
class LLMStreamChunk:
    """
    LLM 스트리밍 응답의 조각 하나

    delta 는 이번 조각에서 새로 생성된 텍스트. usage 값들은 스트림 마지막에
    provider가 보고하는 사용량 조각에서만 채워지고(그 외에는 None/0), 그 전
    조각들은 delta만 갖는다.
    """

    delta: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int = 0


@dataclass(slots=True)
class LLMAnswer:
    """
    스트림을 모두 모은 최종 생성 결과 + 토큰 사용량

    reasoning_tokens는 추론 모델이 아니면 0(provider가 값을 안 주면 0으로 채움).
    """

    content: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int = 0


@dataclass(slots=True)
class Citation:
    """
    답변 근거로 인용된 청크 정보
    """

    chunk_id: str
    document_id: str
    filename: str
    snippet: str


@dataclass(slots=True)
class ChatTurnResult:
    """
    한 턴(질문 1회)의 최종 결과: 답변 + 인용 목록
    """

    content: str
    citations: list[Citation] = field(default_factory=list)
