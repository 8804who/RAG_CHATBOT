from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ChatMessageRole(str, Enum):
    """채팅 메시지 발화자(사용자/어시스턴트)."""

    USER = "user"
    ASSISTANT = "assistant"


class Chat(Base):
    """
    채팅 세션

    한 채팅은 생성 시 채팅 모델을 선택해 고정한다(이후 변경 불가).
    collection_name은 선택: 지정하면 검색이 해당 컬렉션에 고정되고,
    None이면 에이전트가 매 질의마다 검색 대상 컬렉션을 스스로 고른다.
    """

    __tablename__ = "chats"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    collection_name: Mapped[str | None] = mapped_column(String(255), index=True)
    chat_model: Mapped[str] = mapped_column(String(255))
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ChatMessage(Base):
    """
    채팅 메시지(사용자 질문 / 어시스턴트 답변)
    """

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("chats.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_chat_messages_chat_id_created_at", "chat_id", "created_at"),
    )
