from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Chat, ChatMessage, ChatMessageRole


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
