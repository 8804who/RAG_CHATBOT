import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.chat_repository import ChatRepository


def _make_db() -> AsyncMock:
    """AsyncSession spec으로 add는 동기, commit/refresh/execute는 비동기로 구분."""
    return AsyncMock(spec=AsyncSession)


def test_create_chat_success():
    # 채팅 생성 시 컬렉션·모델을 고정하고 uuid 기반 id를 발급한다.
    repo = ChatRepository()
    db = _make_db()

    chat = asyncio.run(
        repo.create_chat(
            db, collection_name="docs", chat_model="gpt-4o-mini", owner_id=1
        )
    )

    assert chat.collection_name == "docs"
    assert chat.chat_model == "gpt-4o-mini"
    assert chat.owner_id == 1
    assert len(chat.id) == 32  # uuid4().hex
    db.add.assert_called_once_with(chat)
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(chat)


def test_get_chat_success_with_missing_chat():
    # 존재하지 않는 chat_id는 예외 대신 None을 반환한다.
    repo = ChatRepository()
    db = _make_db()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    found = asyncio.run(repo.get_chat(db, "missing"))

    assert found is None


def test_add_turn_messages_success_with_single_commit():
    """
    턴 메시지 저장(성공) - 사용자 질문 + 답변을 한 트랜잭션으로 저장

    입력 데이터
        - chat_id = "c1", query = "질문", answer = "답변", citations 1건

    예상 출력 데이터
        - user → assistant 순서로 2건 add, commit 1회
        - 사용자 메시지 citations None, 답변 citations 유지
    """
    repo = ChatRepository()
    db = _make_db()

    user_message, assistant_message = asyncio.run(
        repo.add_turn_messages(
            db,
            chat_id="c1",
            query="질문",
            answer="답변",
            citations=[{"chunk_id": "c1"}],
        )
    )

    assert (user_message.role, user_message.content) == ("user", "질문")
    assert user_message.citations is None
    assert (assistant_message.role, assistant_message.content) == ("assistant", "답변")
    assert assistant_message.citations == [{"chunk_id": "c1"}]
    db.add_all.assert_called_once_with([user_message, assistant_message])
    db.commit.assert_awaited_once()


def test_add_turn_messages_failed_with_commit_error():
    """
    턴 메시지 저장(실패) - 커밋 실패 시 예외 전파(부분 저장 없음)

    입력 데이터
        - db.commit이 RuntimeError

    예상 출력 데이터
        - RuntimeError 전파
    """
    repo = ChatRepository()
    db = _make_db()
    db.commit.side_effect = RuntimeError("db down")

    with pytest.raises(RuntimeError):
        asyncio.run(
            repo.add_turn_messages(
                db, chat_id="c1", query="질문", answer="답변", citations=[]
            )
        )


def test_list_messages_success_with_oldest_first_order():
    """
    채팅 메시지 목록 조회(성공) - 오래된 순(created_at, id) 정렬

    입력 데이터
        - chat_id = "c1"

    예상 출력 데이터
        - chat_id 필터 + created_at, id 오름차순 쿼리, 조회 결과 그대로 반환
    """
    repo = ChatRepository()
    db = _make_db()
    rows = [MagicMock(), MagicMock()]
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    db.execute.return_value = result

    messages = asyncio.run(repo.list_messages(db, "c1"))

    assert messages == rows
    sql = str(db.execute.call_args.args[0])
    assert "chat_messages.chat_id = :chat_id_1" in sql
    assert "ORDER BY chat_messages.created_at, chat_messages.id" in sql


def test_list_messages_success_with_empty_chat():
    """
    채팅 메시지 목록 조회(성공) - 메시지 없는 채팅

    입력 데이터
        - chat_id = "c1", 저장된 메시지 없음

    예상 출력 데이터
        - 빈 리스트
    """
    repo = ChatRepository()
    db = _make_db()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result

    assert asyncio.run(repo.list_messages(db, "c1")) == []
