import asyncio
from unittest.mock import MagicMock

import pytest

from exceptions.chat import UnsupportedChatModelError
from schemes.dto.chat import LLMStreamChunk
from schemes.dto.retrieval import RetrievedChunk
from services.generation.generation_service import GenerationService


def _fake_client(chunks: list[LLMStreamChunk]) -> MagicMock:
    """chunks를 순서대로 내보내는 가짜 LLMClient."""

    async def stream_answer(system, messages):
        for chunk in chunks:
            yield chunk

    client = MagicMock()
    client.stream_answer = stream_answer
    return client


def test_answer_success_with_context():
    # 스트림 델타를 이어붙이고, 마지막 사용량 조각에서 토큰 수를 채운다.
    registry = MagicMock()
    registry.resolve.return_value = _fake_client(
        [
            LLMStreamChunk(delta="안녕"),
            LLMStreamChunk(delta="하세요"),
            LLMStreamChunk(delta="", input_tokens=10, output_tokens=5, reasoning_tokens=0),
        ]
    )
    service = GenerationService(chat_model_registry=registry)
    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            document_id="d1",
            filename="a.txt",
            chunk_index=0,
            text="본문",
            score=0.9,
        )
    ]

    result = asyncio.run(service.answer("gpt-4o-mini", "질문", chunks))

    assert result.content == "안녕하세요"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    registry.resolve.assert_called_once_with("gpt-4o-mini")


def test_answer_success_with_empty_chunks():
    # 검색 결과가 없어도 플레이스홀더 컨텍스트로 정상 답변한다.
    registry = MagicMock()
    captured: dict = {}

    async def stream_answer(system, messages):
        captured["messages"] = messages
        yield LLMStreamChunk(delta="모름", input_tokens=3, output_tokens=1)

    client = MagicMock()
    client.stream_answer = stream_answer
    registry.resolve.return_value = client
    service = GenerationService(chat_model_registry=registry)

    result = asyncio.run(service.answer("gpt-4o-mini", "질문", []))

    assert result.content == "모름"
    assert "관련 문서를 찾지 못했습니다" in captured["messages"][0]["content"]


def test_answer_failed_with_unsupported_model():
    # 레지스트리가 미등록 모델에 대해 던지는 예외가 그대로 전파된다.
    registry = MagicMock()
    registry.resolve.side_effect = UnsupportedChatModelError(
        message="chat model 'unknown' is not registered", code_path="p"
    )
    service = GenerationService(chat_model_registry=registry)

    with pytest.raises(UnsupportedChatModelError):
        asyncio.run(service.answer("unknown", "질문", []))
