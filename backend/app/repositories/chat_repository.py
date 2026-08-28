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

    async def add_message(
        self,
        db: AsyncSession,
        *,
        chat_id: str,
        role: ChatMessageRole,
        content: str,
        citations: list[dict] | None = None,
    ) -> ChatMessage:
        """
        채팅 메시지 저장(사용자 질문 또는 어시스턴트 답변)

        Parameters:
            db(AsyncSession): DB 세션
            chat_id(str): 소속 채팅 id
            role(ChatMessageRole): 발화자
            content(str): 메시지 본문
            citations(list[dict] | None): 답변 근거(어시스턴트 메시지만 해당)

        Returns:
            ChatMessage: 저장된 메시지
        """
        message = ChatMessage(
            chat_id=chat_id,
            role=role.value,
            content=content,
            citations=citations,
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)
        return message
