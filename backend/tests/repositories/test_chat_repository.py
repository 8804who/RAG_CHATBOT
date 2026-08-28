import asyncio
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from models import ChatMessageRole
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


def test_add_message_success_with_citations():
    # 어시스턴트 메시지는 citations(list[dict])와 함께 저장된다.
    repo = ChatRepository()
    db = _make_db()

    message = asyncio.run(
        repo.add_message(
            db,
            chat_id="c1",
            role=ChatMessageRole.ASSISTANT,
            content="답변",
            citations=[{"chunk_id": "c1"}],
        )
    )

    assert message.chat_id == "c1"
    assert message.role == "assistant"
    assert message.citations == [{"chunk_id": "c1"}]
    db.add.assert_called_once_with(message)


def test_add_message_success_with_user_role_and_no_citations():
    # 사용자 메시지는 citations 없이 저장된다.
    repo = ChatRepository()
    db = _make_db()

    message = asyncio.run(
        repo.add_message(db, chat_id="c1", role=ChatMessageRole.USER, content="질문")
    )

    assert message.role == "user"
    assert message.citations is None
