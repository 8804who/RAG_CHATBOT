from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class DocumentStatus(str, Enum):
    """비동기 인제스트 문서 처리 상태."""

    UPLOADED = "UPLOADED"  # 업로드 접수, documents.uploaded 발행 직후
    PARSING = "PARSING"  # Parser Worker가 청킹 중/완료
    EMBEDDING = "EMBEDDING"  # Embed Worker가 임베딩 중
    INDEXED = "INDEXED"  # 모든 청크 Qdrant 적재 완료
    FAILED = "FAILED"  # 어느 단계에서든 실패(DLQ로 격리)


class DocumentRecord(Base):
    """
    문서 인제스트 상태
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    collection_name: Mapped[str] = mapped_column(String(255), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    requester_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    requester_email: Mapped[str | None] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(
        String(16), default=DocumentStatus.UPLOADED.value
    )
    total_chunks: Mapped[int | None] = mapped_column(Integer)
    indexed_chunks: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
