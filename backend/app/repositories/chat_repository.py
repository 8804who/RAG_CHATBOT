from uuid import uuid4

from sqlalchemy import delete, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from core.constants import CHAT_TITLE_MAX_LENGTH
from models import Chat, ChatMessage, ChatMessageRole
from schemes.dto.chat import ChatSummary

# 제목 잘림 여부를 서비스가 판단할 수 있도록 상한보다 1글자 더 가져온다.
_TITLE_PREVIEW_LENGTH = CHAT_TITLE_MAX_LENGTH + 1


class ChatRepository:
    """
    채팅 세션·메시지 관리
    """

    def __init__(self) -> None:
        pass

    async def create_chat(
        self,
        db: AsyncSession,
        *,
        collection_name: str,
        chat_model: str,
        owner_id: int | None,
    ) -> Chat:
        """
        채팅 세션 생성(컬렉션·채팅 모델을 이 시점에 고정)

        Parameters:
            db(AsyncSession): DB 세션
            collection_name(str): 검색 대상 컬렉션
            chat_model(str): 이 채팅에서 고정 사용할 생성 모델
            owner_id(int | None): 채팅 소유자 user id

        Returns:
            Chat: 생성된 채팅 세션
        """
        chat = Chat(
            id=uuid4().hex,
            collection_name=collection_name,
            chat_model=chat_model,
            owner_id=owner_id,
        )
        db.add(chat)
        await db.commit()
        await db.refresh(chat)
        return chat

    async def get_chat(self, db: AsyncSession, chat_id: str) -> Chat | None:
        """
        채팅 세션 조회

        Parameters:
            db(AsyncSession): DB 세션
            chat_id(str): 조회할 채팅 id

        Returns:
            Chat | None: 채팅 세션(없으면 None)
        """
        stmt = select(Chat).where(Chat.id == chat_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def add_turn_messages(
        self,
        db: AsyncSession,
        *,
        chat_id: str,
        query: str,
        answer: str,
        citations: list[dict],
    ) -> tuple[ChatMessage, ChatMessage]:
        """
        성공한 한 턴의 사용자 질문 + 어시스턴트 답변을 한 트랜잭션으로 저장

        Parameters:
            db(AsyncSession): DB 세션
            chat_id(str): 소속 채팅 id
            query(str): 사용자 질문
            answer(str): 어시스턴트 답변
            citations(list[dict]): 답변 근거

        Returns:
            tuple[ChatMessage, ChatMessage]: (사용자 메시지, 답변 메시지)
        """
        user_message = ChatMessage(
            chat_id=chat_id, role=ChatMessageRole.USER.value, content=query
        )
        assistant_message = ChatMessage(
            chat_id=chat_id,
            role=ChatMessageRole.ASSISTANT.value,
            content=answer,
            citations=citations,
        )
        db.add_all([user_message, assistant_message])
        await db.commit()
        return user_message, assistant_message

    async def list_messages(self, db: AsyncSession, chat_id: str) -> list[ChatMessage]:
        """
        채팅 메시지 목록 조회(오래된 순)

        같은 트랜잭션에 저장된 질문·답변은 created_at이 같으므로 id로 순서를 보장한다.

        Parameters:
            db(AsyncSession): DB 세션
            chat_id(str): 채팅 id

        Returns:
            list[ChatMessage]: 메시지 목록
        """
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_chats(
        self, db: AsyncSession, *, owner_id: int, limit: int
    ) -> list[ChatSummary]:
        """
        소유자의 채팅 목록 조회(최근 활동순, 한 문장으로 N+1 없이)

        마지막 메시지 시각은 LATERAL MAX 집계로, 제목은 첫 사용자 메시지(created_at, id
        오름차순)를 공백 정규화해 상한+1 글자만 가져오는 상관 서브쿼리로 구한다.
        둘 다 ix_chat_messages_chat_id_created_at 인덱스를 탄다.

        Parameters:
            db(AsyncSession): DB 세션
            owner_id(int): 채팅 소유자 user id
            limit(int): 최대 반환 개수

        Returns:
            list[ChatSummary]: 채팅 요약 목록(title은 공백 정규화된 미리보기)
        """
        last_message = (
            select(func.max(ChatMessage.created_at).label("last_message_at"))
            .where(ChatMessage.chat_id == Chat.id)
            .lateral()
        )
        first_message = aliased(ChatMessage)
        normalized_content = func.btrim(
            func.regexp_replace(first_message.content, r"\s+", " ", "g")
        )
        title_preview = (
            select(func.left(normalized_content, _TITLE_PREVIEW_LENGTH))
            .where(
                first_message.chat_id == Chat.id,
                first_message.role == ChatMessageRole.USER.value,
            )
            .order_by(first_message.created_at, first_message.id)
            .limit(1)
            .scalar_subquery()
        )
        stmt = (
            select(
                Chat.id,
                title_preview.label("title"),
                Chat.chat_model,
                Chat.collection_name,
                Chat.created_at,
                last_message.c.last_message_at,
            )
            .join(last_message, true())
            .where(Chat.owner_id == owner_id)
            .order_by(
                func.coalesce(last_message.c.last_message_at, Chat.created_at).desc(),
                Chat.id,
            )
            .limit(limit)
        )
        result = await db.execute(stmt)
        return [
            ChatSummary(
                id=row.id,
                title=row.title,
                chat_model=row.chat_model,
                collection_name=row.collection_name,
                created_at=row.created_at,
                last_message_at=row.last_message_at,
            )
            for row in result.all()
        ]

    async def delete_chat(self, db: AsyncSession, chat_id: str) -> None:
        """
        채팅 삭제(chat_messages는 FK ON DELETE CASCADE로 함께 삭제)

        Parameters:
            db(AsyncSession): DB 세션
            chat_id(str): 삭제할 채팅 id
        """
        await db.execute(delete(Chat).where(Chat.id == chat_id))
        await db.commit()
