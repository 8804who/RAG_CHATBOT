from sqlalchemy.ext.asyncio import AsyncSession

from core.constants import DEFAULT_CURRENCY
from repositories import LogRepository, PricingRepository
from schemes.dto.usage import ChatUsageRow, EmbeddingUsageRow, ModelPrice
from schemes.responses import (
    ChatUsageStat,
    EmbeddingUsageStat,
    UsageStatsResponse,
)

_TOKENS_PER_UNIT = 1_000_000


class UsageStatsService:
    """
    마이페이지 토큰 사용량/비용 통계 오케스트레이션
    """

    def __init__(
        self,
        log_repository: LogRepository,
        pricing_repository: PricingRepository,
    ) -> None:
        self._log_repository = log_repository
        self._pricing_repository = pricing_repository

    async def get_user_stats(
        self, db: AsyncSession, requester_id: int
    ) -> UsageStatsResponse:
        """
        사용자별 모델 그룹핑 사용량/비용 통계 조회

        Parameters:
            db(AsyncSession): DB 세션
            requester_id(int): 통계 대상 user id

        Returns:
            UsageStatsResponse: 모델별 임베딩/채팅 사용량 + 비용 합계
        """
        embedding_rows = await self._log_repository.aggregate_embedding_usage(
            db, requester_id
        )
        chat_rows = await self._log_repository.aggregate_chat_usage(db, requester_id)
        prices = await self._pricing_repository.get_price_map(db)

        embedding_stats = [
            self._embedding_stat(row, prices.get(row.model)) for row in embedding_rows
        ]
        chat_stats = [self._chat_stat(row, prices.get(row.model)) for row in chat_rows]

        total_cost = sum(stat.cost or 0.0 for stat in embedding_stats) + sum(
            stat.cost or 0.0 for stat in chat_stats
        )
        return UsageStatsResponse(
            embedding=embedding_stats,
            chat=chat_stats,
            total_cost=round(total_cost, 6),
            currency=DEFAULT_CURRENCY,
        )

    def _embedding_stat(
        self, row: EmbeddingUsageRow, price: ModelPrice | None
    ) -> EmbeddingUsageStat:
        """임베딩 집계 행 + 단가 → 사용량/비용 통계(단가 없으면 cost=None)."""
        cost = None
        currency = None
        if price is not None:
            cost = round(
                row.total_tokens / _TOKENS_PER_UNIT * price.input_price_per_1m, 6
            )
            currency = price.currency
        return EmbeddingUsageStat(
            model=row.model,
            total_tokens=row.total_tokens,
            document_count=row.document_count,
            cost=cost,
            currency=currency,
        )

    def _chat_stat(self, row: ChatUsageRow, price: ModelPrice | None) -> ChatUsageStat:
        """채팅 집계 행 + 단가 → 사용량/비용 통계.

        추론(reasoning) 토큰은 출력 단가로 계산
        """
        total_tokens = row.input_tokens + row.output_tokens + row.reasoning_tokens
        cost = None
        currency = None
        if price is not None:
            input_cost = row.input_tokens / _TOKENS_PER_UNIT * price.input_price_per_1m
            output_cost = (
                (row.output_tokens + row.reasoning_tokens)
                / _TOKENS_PER_UNIT
                * price.output_price_per_1m
            )
            cost = round(input_cost + output_cost, 6)
            currency = price.currency
        return ChatUsageStat(
            model=row.model,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            reasoning_tokens=row.reasoning_tokens,
            total_tokens=total_tokens,
            message_count=row.message_count,
            cost=cost,
            currency=currency,
        )
