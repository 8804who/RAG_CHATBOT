import asyncio
import json
from collections.abc import AsyncIterator, Iterator
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
from schemes.dto.chat import (
    ChatHistory,
    ChatStreamEvent,
    ChatSummary,
    ChatTurnResult,
    Citation,
)
from services.agent.agent_orchestrator import _shielded

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


_STREAM_URL = "/api/v1/chats/c1/messages/stream"


async def _events(*events: ChatStreamEvent) -> AsyncIterator[ChatStreamEvent]:
    for event in events:
        yield event


def _sse(text: str) -> list[tuple[str, dict]]:
    """SSE 본문을 (event, data JSON) 목록으로 파싱"""
    frames = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        frames.append((fields["event"], json.loads(fields["data"])))
    return frames


def test_stream_message_success_with_tokens_then_done(orchestrator):
    """
    메시지 스트리밍(성공)

    입력 데이터
        - POST /api/v1/chats/c1/messages/stream, query = "질문"
        - 오케스트레이터 이벤트: token "안녕", token "하세요", done(답변 + 인용 1건)

    예상 출력 데이터
        - 200 text/event-stream, Cache-Control: no-cache, X-Accel-Buffering: no
        - token {"content"} 2건 → done = 비스트리밍 응답과 같은 ChatMessageResponse JSON
    """
    result = ChatTurnResult(
        content="안녕하세요",
        citations=[Citation(source_type="web", title="t", snippet="s", url="u")],
    )
    orchestrator.stream_message.return_value = _events(
        ChatStreamEvent(event="token", content="안녕"),
        ChatStreamEvent(event="token", content="하세요"),
        ChatStreamEvent(event="done", result=result),
    )

    response = TestClient(app).post(_STREAM_URL, json={"query": "질문"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert _sse(response.text) == [
        ("token", {"content": "안녕"}),
        ("token", {"content": "하세요"}),
        (
            "done",
            {
                "role": "assistant",
                "content": "안녕하세요",
                "citations": [
                    {
                        "source_type": "web",
                        "title": "t",
                        "snippet": "s",
                        "document_id": None,
                        "chunk_id": None,
                        "collection_name": None,
                        "url": "u",
                    }
                ],
            },
        ),
    ]
    kwargs = orchestrator.stream_message.call_args.kwargs
    assert (kwargs["chat_id"], kwargs["query"], kwargs["requester"].id) == (
        "c1",
        "질문",
        1,
    )


def test_stream_message_failed_with_error_event(orchestrator):
    """
    메시지 스트리밍(실패) - 스트림 도중 실패

    입력 데이터
        - 오케스트레이터 이벤트: token "부분", error "일시적으로 장애가 발생하였습니다."

    예상 출력 데이터
        - 200 스트림, 마지막 프레임 error {"detail": 문구}
    """
    orchestrator.stream_message.return_value = _events(
        ChatStreamEvent(event="token", content="부분"),
        ChatStreamEvent(event="error", content="일시적으로 장애가 발생하였습니다."),
    )

    response = TestClient(app).post(_STREAM_URL, json={"query": "질문"})

    assert response.status_code == 200
    assert _sse(response.text) == [
        ("token", {"content": "부분"}),
        ("error", {"detail": "일시적으로 장애가 발생하였습니다."}),
    ]


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (ChatNotFoundError, 404),
        (ChatAccessDeniedError, 403),
        (ChatTurnInProgressError, 409),
    ],
)
def test_stream_message_failed_with_pre_stream_error(
    orchestrator, error, expected_status
):
    """
    메시지 스트리밍(실패) - 스트림 시작 전 검증 실패는 일반 JSON 오류

    입력 데이터
        - 오케스트레이터 stream_message가 각 예외

    예상 출력 데이터
        - 각각 404 / 403 / 409, application/json, detail = 사용자용 안내 문구
    """
    orchestrator.stream_message.side_effect = error(
        message=error.response_message, code_path="p"
    )

    response = TestClient(app).post(_STREAM_URL, json={"query": "질문"})

    assert response.status_code == expected_status
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": error.response_message}


def test_stream_message_failed_with_invalid_body(orchestrator):
    """
    메시지 스트리밍(실패) - 요청 본문 검증 실패

    입력 데이터
        - POST /api/v1/chats/c1/messages/stream, 본문 {}

    예상 출력 데이터
        - 422 JSON, 오케스트레이터 미호출
    """
    response = TestClient(app).post(_STREAM_URL, json={})

    assert response.status_code == 422
    orchestrator.stream_message.assert_not_called()


def test_stream_message_failed_with_client_disconnect(orchestrator):
    """
    메시지 스트리밍(실패) - 첫 토큰 후 클라이언트 연결 끊김(미들웨어 포함 실제 ASGI 앱)

    입력 데이터
        - 오케스트레이터 스트림: token "부분" 후 LLM 대기(끝나지 않음)
        - 첫 본문 전송 뒤 receive가 http.disconnect(uvicorn과 같은 spec_version 2.3)

    예상 출력 데이터
        - 앱 호출이 끝나고, 오케스트레이터 스트림의 await 정리(서비스 shield 사용)가 끝까지 실행됨
    """
    closed = asyncio.Event()

    async def cleanup() -> None:
        await asyncio.sleep(0)
        closed.set()

    async def hanging_events() -> AsyncIterator[ChatStreamEvent]:
        try:
            yield ChatStreamEvent(event="token", content="부분")
            await asyncio.Event().wait()
        finally:
            await _shielded(cleanup())

    orchestrator.stream_message.return_value = hanging_events()

    async def scenario() -> list[dict]:
        sent: list[dict] = []
        first_body = asyncio.Event()
        requested = False

        async def receive() -> dict:
            nonlocal requested
            if not requested:
                requested = True
                body = json.dumps({"query": "질문"}).encode()
                return {"type": "http.request", "body": body, "more_body": False}
            await first_body.wait()
            return {"type": "http.disconnect"}

        async def send(message: dict) -> None:
            sent.append(message)
            if message["type"] == "http.response.body" and message.get("body"):
                first_body.set()

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": _STREAM_URL,
            "raw_path": _STREAM_URL.encode(),
            "query_string": b"",
            "headers": [(b"content-type", b"application/json"), (b"host", b"test")],
            "client": ("127.0.0.1", 1),
            "server": ("test", 80),
        }
        await asyncio.wait_for(app(scope, receive, send), timeout=5)
        await asyncio.wait_for(closed.wait(), timeout=5)
        return sent

    sent = asyncio.run(scenario())

    assert sent[0]["status"] == 200
    assert closed.is_set()
