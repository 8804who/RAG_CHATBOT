from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from dependencies.auth import get_current_user
from dependencies.db import get_db_session
from dependencies.services import get_chat_orchestrator
from exceptions.chat import (
    ChatAccessDeniedError,
    ChatNotFoundError,
    ChatTurnInProgressError,
)
from main import app
from models import ChatMessage, User
from schemes.dto.chat import ChatHistory, ChatTurnResult

_CREATED_AT = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)


@pytest.fixture
def orchestrator() -> Iterator[AsyncMock]:
    """채팅 오케스트레이터·DB 세션·현재 사용자를 대역으로 바꾼 앱 의존성."""
    fake = AsyncMock()

    async def fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_chat_orchestrator] = lambda: fake
    app.dependency_overrides[get_db_session] = fake_db
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1, google_sub="sub", email="a@b.com"
    )
    yield fake
    app.dependency_overrides.clear()


def _message(role: str, content: str, citations: list | None) -> ChatMessage:
    return ChatMessage(
        chat_id="c1",
        role=role,
        content=content,
        citations=citations,
        created_at=_CREATED_AT,
    )


def test_get_messages_success_with_oldest_first_history(orchestrator):
    """
    채팅 이력 조회(성공)

    입력 데이터
        - GET /api/v1/chats/c1/messages, 저장된 메시지 2건(질문 → 답변)

    예상 출력 데이터
        - 200, chat_model/collection_name + 메시지 2건(role, content, citations, created_at)
    """
    orchestrator.get_messages.return_value = ChatHistory(
        chat_model="gpt-4o-mini",
        collection_name="docs",
        messages=[
            _message("user", "질문", None),
            _message(
                "assistant",
                "답변",
                [{"source_type": "document", "title": "a.txt", "snippet": "본문"}],
            ),
        ],
    )

    response = TestClient(app).get("/api/v1/chats/c1/messages")

    assert response.status_code == 200
    body = response.json()
    assert body["chat_model"] == "gpt-4o-mini"
    assert body["collection_name"] == "docs"
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assert body["messages"][0]["citations"] == []
    assert body["messages"][1]["citations"][0]["title"] == "a.txt"
    assert body["messages"][1]["created_at"].startswith("2026-11-26T12:00:00")
    assert orchestrator.get_messages.call_args.kwargs["chat_id"] == "c1"


def test_get_messages_failed_with_missing_chat(orchestrator):
    """
    채팅 이력 조회(실패) - 존재하지 않는 채팅

    입력 데이터
        - GET /api/v1/chats/missing/messages

    예상 출력 데이터
        - 404
    """
    orchestrator.get_messages.side_effect = ChatNotFoundError(
        message="해당 채팅이 존재하지 않습니다", code_path="p"
    )

    response = TestClient(app).get("/api/v1/chats/missing/messages")

    assert response.status_code == 404


def test_get_messages_failed_with_other_users_chat(orchestrator):
    """
    채팅 이력 조회(실패) - 다른 사용자의 채팅

    입력 데이터
        - GET /api/v1/chats/c1/messages, 소유자 아님

    예상 출력 데이터
        - 403
    """
    orchestrator.get_messages.side_effect = ChatAccessDeniedError(
        message="해당 채팅에 접근할 권한이 없습니다", code_path="p"
    )

    response = TestClient(app).get("/api/v1/chats/c1/messages")

    assert response.status_code == 403


def test_send_message_failed_with_turn_in_progress(orchestrator):
    """
    메시지 전송(실패) - 같은 채팅의 이전 턴 진행 중

    입력 데이터
        - POST /api/v1/chats/c1/messages, 오케스트레이터가 ChatTurnInProgressError

    예상 출력 데이터
        - 409, detail = 사용자용 안내 문구
    """
    orchestrator.send_message.side_effect = ChatTurnInProgressError(
        message=ChatTurnInProgressError.response_message, code_path="p"
    )

    response = TestClient(app).post("/api/v1/chats/c1/messages", json={"query": "질문"})

    assert response.status_code == 409
    assert response.json()["detail"] == ChatTurnInProgressError.response_message


def test_send_message_success_with_answer(orchestrator):
    """
    메시지 전송(성공)

    입력 데이터
        - POST /api/v1/chats/c1/messages, query = "질문"

    예상 출력 데이터
        - 200, role = "assistant", content = "답변"
    """
    orchestrator.send_message.return_value = ChatTurnResult(content="답변")

    response = TestClient(app).post("/api/v1/chats/c1/messages", json={"query": "질문"})

    assert response.status_code == 200
    assert response.json() == {"role": "assistant", "content": "답변", "citations": []}
