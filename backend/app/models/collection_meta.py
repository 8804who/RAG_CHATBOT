from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class CollectionMeta(Base):
    """
    컬렉션 ↔ 임베딩 모델 정보

    한 컬렉션의 모든 벡터는 동일 임베딩 모델/차원이어야하므로,
    생성 시 선택한 임베딩 모델을 저장하고 재사용
    """

    __tablename__ = "collection_meta"

    collection_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    embedding_model: Mapped[str] = mapped_column(String(255))
    dimension: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
