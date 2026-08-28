from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from clients.llm.llm_client import LLMClient
from core.constants import DEFAULT_CHAT_MAX_COMPLETION_TOKENS
from schemes.dto.chat import LLMStreamChunk


class OpenAILLMClient(LLMClient):
    """OpenAI Chat Completions 구현.

    AsyncOpenAI는 네이티브 async이므로 스레드풀이 필요 없다. 클라이언트는
    애플리케이션 시작 시 warmup으로 생성한다(원격 API라 로컬 모델 로딩은
    없고 httpx 풀만 준비한다). API 키가 없으면 warmup이 실패하므로,
    레지스트리가 개별 provider 단위로 격리해 시작을 막지 않는다.
    """

    def __init__(self, model_name: str, api_key: str | None) -> None:
        self._model_name = model_name
        self._api_key = api_key
        self._client = AsyncOpenAI(api_key=self._api_key)

    @property
    def model_name(self) -> str:
        return self._model_name

    async def stream_answer(
        self, system: str, messages: list[dict[str, str]]
    ) -> AsyncIterator[LLMStreamChunk]:
        """OpenAI Chat Completions 스트리밍.

        stream_options.include_usage로 스트림 마지막에 사용량 전용 조각을
        받는다(그 조각은 choices가 비어 있음). max_completion_tokens는
        프론트 값을 신뢰하지 않고 서버에서 고정 상한을 강제한다.
        """
        stream = await self._client.chat.completions.create(
            model=self._model_name,
            messages=[{"role": "system", "content": system}, *messages],
            max_completion_tokens=DEFAULT_CHAT_MAX_COMPLETION_TOKENS,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield LLMStreamChunk(delta=delta)
            if chunk.usage is not None:
                reasoning_tokens = (
                    chunk.usage.completion_tokens_details.reasoning_tokens
                    if chunk.usage.completion_tokens_details is not None
                    else None
                )
                yield LLMStreamChunk(
                    delta="",
                    input_tokens=chunk.usage.prompt_tokens,
                    output_tokens=chunk.usage.completion_tokens,
                    reasoning_tokens=reasoning_tokens or 0,
                )
