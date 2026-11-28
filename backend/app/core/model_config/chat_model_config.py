from langchain_openai import ChatOpenAI

from core.config import config
from core.constants import (
    CHAT_MODEL_MAX_RETRIES,
    CHAT_MODEL_TIMEOUT_SECONDS,
    DEFAULT_CHAT_MAX_COMPLETION_TOKENS,
)
from schemes.dto.chat import RegisteredChatModel


def _openai_chat_model(model: str) -> ChatOpenAI:
    """
    서버 강제 상한(응답 토큰·타임아웃·재시도)과 스트리밍 사용량 수집을 적용한 OpenAI 채팅 모델 생성

    Parameters:
        model(str): OpenAI 모델명

    Returns:
        ChatOpenAI: 채팅 모델
    """
    return ChatOpenAI(
        model=model,
        api_key=config.OPENAI_API_KEY,
        max_tokens=DEFAULT_CHAT_MAX_COMPLETION_TOKENS,
        timeout=CHAT_MODEL_TIMEOUT_SECONDS,
        max_retries=CHAT_MODEL_MAX_RETRIES,
        # 스트리밍 턴에서도 마지막 chunk로 토큰 사용량을 받아 사용량 로그를 남긴다(D-018e)
        stream_usage=True,
    )


openai_gpt4o_mini = _openai_chat_model("gpt-4o-mini")
openai_gpt4o = _openai_chat_model("gpt-4o")

chat_model_catalog = {
    "gpt-4o-mini": (
        RegisteredChatModel(name="gpt-4o-mini", provider="openai"),
        openai_gpt4o_mini,
    ),
    "gpt-4o": (
        RegisteredChatModel(name="gpt-4o", provider="openai"),
        openai_gpt4o,
    ),
}
