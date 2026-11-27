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
from schemes.dto.chat import ChatHistory, ChatSummary, ChatTurnResult

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


def test_list_chats_success_with_summaries(orchestrator):
    """
    채팅 목록 조회(성공)

    입력 데이터
        - GET /api/v1/chats, 메시지 있는 채팅 1건 + 빈 채팅 1건

    예상 출력 데이터
        - 200, chats 2건(id, title, chat_model, collection_name, created_at, last_message_at),
          빈 채팅은 title/last_message_at null, 요청자 전달
    """
    orchestrator.list_chats.return_value = [
        ChatSummary(
            id="c2",
            title="최근 질문",
            chat_model="gpt-4o-mini",
            collection_name="docs",
            created_at=_CREATED_AT,
            last_message_at=_CREATED_AT,
        ),
        ChatSummary(
            id="c1",
            title=None,
            chat_model="gpt-4o-mini",
            collection_name=None,
            created_at=_CREATED_AT,
            last_message_at=None,
        ),
    ]

    response = TestClient(app).get("/api/v1/chats")

    assert response.status_code == 200
    chats = response.json()["chats"]
    assert [chat["id"] for chat in chats] == ["c2", "c1"]
    assert chats[0]["title"] == "최근 질문"
    assert chats[0]["collection_name"] == "docs"
    assert chats[0]["last_message_at"].startswith("2026-11-26T12:00:00")
    assert chats[1]["title"] is None
    assert chats[1]["last_message_at"] is None
    assert orchestrator.list_chats.call_args.kwargs["requester"].id == 1


def test_list_chats_success_with_no_chats(orchestrator):
    """
    채팅 목록 조회(성공) - 채팅 없음

    입력 데이터
        - GET /api/v1/chats, 오케스트레이터가 빈 목록

    예상 출력 데이터
        - 200, {"chats": []}
    """
    orchestrator.list_chats.return_value = []

    response = TestClient(app).get("/api/v1/chats")

    assert response.status_code == 200
    assert response.json() == {"chats": []}


def test_list_chats_failed_with_unauthenticated(orchestrator):
    """
    채팅 목록 조회(실패) - 세션 쿠키 없음

    입력 데이터
        - GET /api/v1/chats, 실제 인증 의존성(쿠키 없음)

    예상 출력 데이터
        - 401, 오케스트레이터 미호출
    """
    app.dependency_overrides.pop(get_current_user)

    response = TestClient(app).get("/api/v1/chats")

    assert response.status_code == 401
    orchestrator.list_chats.assert_not_awaited()


def test_delete_chat_success_with_no_content(orchestrator):
    """
    채팅 삭제(성공)

    입력 데이터
        - DELETE /api/v1/chats/c1

    예상 출력 데이터
        - 204, 본문 없음, chat_id·요청자 전달
    """
    orchestrator.delete_chat.return_value = None

    response = TestClient(app).delete("/api/v1/chats/c1")

    assert response.status_code == 204
    assert response.content == b""
    kwargs = orchestrator.delete_chat.call_args.kwargs
    assert (kwargs["chat_id"], kwargs["requester"].id) == ("c1", 1)


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (ChatNotFoundError, 404),
        (ChatAccessDeniedError, 403),
        (ChatTurnInProgressError, 409),
    ],
)
def test_delete_chat_failed_with_service_error(orchestrator, error, expected_status):
    """
    채팅 삭제(실패) - 없는 채팅 / 남의 채팅 / 턴 진행 중

    입력 데이터
        - DELETE /api/v1/chats/c1, 오케스트레이터가 각 예외

    예상 출력 데이터
        - 각각 404 / 403 / 409, detail = 사용자용 안내 문구
    """
    orchestrator.delete_chat.side_effect = error(
        message=error.response_message, code_path="p"
    )

    response = TestClient(app).delete("/api/v1/chats/c1")

    assert response.status_code == expected_status
    assert response.json()["detail"] == error.response_message
