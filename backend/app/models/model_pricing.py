from datetime import datetime

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ModelPricing(Base):
    """
    모델별 토큰 단가

    100만(1M) 토큰당 USD 단가를 모델 이름 기준으로 보관
    임베딩 모델은 출력 개념이 없으므로 output_price_per_1m 은 0 고정
    """

    __tablename__ = "model_pricing"

    model: Mapped[str] = mapped_column(String(255), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # embedding | chat
    input_price_per_1m: Mapped[float] = mapped_column(Float, default=0.0)
    output_price_per_1m: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    effective_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
