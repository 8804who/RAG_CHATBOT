from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models import ModelPricing
from schemes.dto.usage import ModelPrice


class PricingRepository:
    """
    모델 토큰 비용 관리
    """

    def __init__(self) -> None:
        pass

    async def get_price_map(self, db: AsyncSession) -> dict[str, ModelPrice]:
        """
        모델 별 토큰 비용 조회

        Parameters:
            db(AsyncSession): DB 세션

        Returns:
            dict[str, ModelPrice]: 모델별 단가(등록되지 않은 모델은 키 없음)
        """
        result = await db.execute(select(ModelPricing))
        return {
            row.model: ModelPrice(
                input_price_per_1m=row.input_price_per_1m,
                output_price_per_1m=row.output_price_per_1m,
                currency=row.currency,
            )
            for row in result.scalars().all()
        }

    async def upsert_defaults(
        self, db: AsyncSession, rows: list[dict[str, object]]
    ) -> None:
        """
        기본 단가 시딩(멱등 upsert)

        이미 존재하는 모델은 단가·통화를 최신 기본값으로 갱신한다(런타임 수동
        수정분이 있으면 재시작 시 되돌아갈 수 있으므로, 운영에서는 시드 값을
        기본값으로만 유지).

        Parameters:
            db(AsyncSession): DB 세션
            rows(list[dict]): model_pricing 컬럼 값 목록
        """
        if not rows:
            return
        stmt = insert(ModelPricing).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[ModelPricing.model],
            set_={
                "kind": stmt.excluded.kind,
                "input_price_per_1m": stmt.excluded.input_price_per_1m,
                "output_price_per_1m": stmt.excluded.output_price_per_1m,
                "currency": stmt.excluded.currency,
            },
        )
        await db.execute(stmt)
        await db.commit()
