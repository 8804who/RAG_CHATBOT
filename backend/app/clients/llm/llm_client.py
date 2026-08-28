from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from schemes.dto.chat import LLMStreamChunk


class LLMClient(ABC):
    """채팅 LLM provider 인터페이스.

    provider를 추가 시, 인터페이스 구현 후 ChatModelRegistry에 등록
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        모델 식별자
        """
        ...

    @abstractmethod
    def stream_answer(
        self, system: str, messages: list[dict[str, str]]
    ) -> AsyncIterator[LLMStreamChunk]:
        """
        이 client에 고정된 모델로 답변 토큰을 스트리밍한다.

        Parameters:
            system(str): 시스템 지시
            messages(list[dict[str, str]]): 대화 메시지({"role", "content"})

        Returns:
            AsyncIterator[LLMStreamChunk]: 텍스트 조각(및 마지막에 사용량) 스트림
        """
        ...
