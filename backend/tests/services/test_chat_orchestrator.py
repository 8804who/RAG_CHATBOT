import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from exceptions.chat import (
    ChatAccessDeniedError,
    ChatNotFoundError,
    UnsupportedChatModelError,
)
from exceptions.document import CollectionMetaNotFoundError
from models import Chat, User
from schemes.dto.chat import LLMAnswer
from schemes.dto.retrieval import RetrievedChunk
from services.chat.chat_orchestrator import ChatOrchestrator


def _make_orchestrator(**overrides):
    deps = dict(
        chat_repository=AsyncMock(),
        chat_model_registry=MagicMock(),
        collection_meta_repository=AsyncMock(),
        retrieval_service=AsyncMock(),
        generation_service=AsyncMock(),
        log_repository=AsyncMock(),
    )
    deps.update(overrides)
    return ChatOrchestrator(**deps), deps


def _chat(owner_id: int | None = 1) -> Chat:
    return Chat(id="c1", collection_name="docs", chat_model="gpt-4o-mini", owner_id=owner_id)


def _user(user_id: int = 1) -> User:
    return User(id=user_id, google_sub="sub", email="a@b.com")


def test_create_chat_success():
    # 모델·컬렉션 매핑이 모두 유효하면 채팅을 생성한다.
    orchestrator, deps = _make_orchestrator()
    deps["collection_meta_repository"].get_collection_metadata.return_value = MagicMock()
    expected_chat = _chat()
    deps["chat_repository"].create_chat.return_value = expected_chat

    result = asyncio.run(
        orchestrator.create_chat(
            AsyncMock(), collection_name="docs", chat_model="gpt-4o-mini", owner_id=1
        )
    )

    assert result is expected_chat
    deps["chat_model_registry"].get_info.assert_called_once_with("gpt-4o-mini")


def test_create_chat_failed_with_unsupported_model():
    # 미등록 채팅 모델이면 컬렉션 조회 없이 즉시 예외를 던진다.
    orchestrator, deps = _make_orchestrator()
    deps["chat_model_registry"].get_info.side_effect = UnsupportedChatModelError(
        message="chat model 'bad' is not registered", code_path="p"
    )

    with pytest.raises(UnsupportedChatModelError):
        asyncio.run(
            orchestrator.create_chat(
                AsyncMock(), collection_name="docs", chat_model="bad", owner_id=1
            )
        )

    deps["collection_meta_repository"].get_collection_metadata.assert_not_awaited()


def test_create_chat_failed_with_missing_collection_meta():
    # 컬렉션에 임베딩 모델 매핑이 없으면 CollectionMetaNotFoundError
    orchestrator, deps = _make_orchestrator()
    deps["collection_meta_repository"].get_collection_metadata.return_value = None

    with pytest.raises(CollectionMetaNotFoundError):
        asyncio.run(
            orchestrator.create_chat(
                AsyncMock(), collection_name="missing", chat_model="gpt-4o-mini", owner_id=1
            )
        )

    deps["chat_repository"].create_chat.assert_not_awaited()


def test_send_message_success_with_call_order():
    # 검색 → 생성 → 메시지 2건 저장 → 사용량 기록 순서로 한 턴을 조립한다.
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()
    chunk = RetrievedChunk(
        chunk_id="c1",
        document_id="d1",
        filename="a.txt",
        chunk_index=0,
        text="본문 내용입니다",
        score=0.9,
    )
    deps["retrieval_service"].retrieve.return_value = [chunk]
    deps["generation_service"].answer.return_value = LLMAnswer(
        content="답변", input_tokens=10, output_tokens=5, reasoning_tokens=0
    )

    result = asyncio.run(
        orchestrator.send_message(AsyncMock(), chat_id="c1", query="질문", requester=_user())
    )

    assert result.content == "답변"
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "c1"
    assert deps["chat_repository"].add_message.await_count == 2
    deps["log_repository"].create_chat_usage_log.assert_awaited_once()
    _, kwargs = deps["log_repository"].create_chat_usage_log.call_args
    assert kwargs["conversation_id"] == "c1"
    assert kwargs["input_tokens"] == 10


def test_send_message_failed_with_missing_chat():
    # 존재하지 않는 chat_id면 ChatNotFoundError
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = None

    with pytest.raises(ChatNotFoundError):
        asyncio.run(
            orchestrator.send_message(
                AsyncMock(), chat_id="missing", query="질문", requester=_user()
            )
        )

    deps["retrieval_service"].retrieve.assert_not_awaited()


def test_send_message_failed_with_other_users_chat():
    # IDOR 방지: 채팅 소유자가 아니면 접근 거부
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat(owner_id=99)

    with pytest.raises(ChatAccessDeniedError):
        asyncio.run(
            orchestrator.send_message(
                AsyncMock(), chat_id="c1", query="질문", requester=_user(user_id=1)
            )
        )

    deps["retrieval_service"].retrieve.assert_not_awaited()
