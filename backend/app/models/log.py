from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class DocumentOperation(str, Enum):
    """문서 관리 요청 타입(삽입/수정/삭제)."""

    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"


class DocumentManageLog(Base):
    """
    문서 관리 이력
    """

    __tablename__ = "document_manage_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    operation: Mapped[str] = mapped_column(String(16), index=True)
    collection_name: Mapped[str] = mapped_column(String(255), index=True)
    filename: Mapped[str | None] = mapped_column(String(512))
    requester_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    requester_email: Mapped[str | None] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(32))
    document_id: Mapped[str | None] = mapped_column(String(64))
    chunk_count: Mapped[int | None] = mapped_column(Integer)
    embedding_model: Mapped[str | None] = mapped_column(String(255))
    embedding_tokens: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ChatUsageLog(Base):
    """
    채팅 토큰 사용 이력
    """

    __tablename__ = "chat_usage_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    requester_email: Mapped[str | None] = mapped_column(String(320))
    model: Mapped[str] = mapped_column(String(255), index=True)
    collection_name: Mapped[str | None] = mapped_column(String(255))
    conversation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
