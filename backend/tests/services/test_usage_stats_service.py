import asyncio
from unittest.mock import AsyncMock

from schemes.dto.usage import ChatUsageRow, EmbeddingUsageRow, ModelPrice
from services.usage.usage_stats_service import UsageStatsService


def _make_service() -> tuple[UsageStatsService, AsyncMock, AsyncMock]:
    log_repo = AsyncMock()
    pricing_repo = AsyncMock()
    service = UsageStatsService(
        log_repository=log_repo, pricing_repository=pricing_repo
    )
    return service, log_repo, pricing_repo


def test_get_user_stats_success_with_pricing():
    # 임베딩/채팅 토큰을 모델별 단가와 곱해 비용을 계산하고 합산한다.
    service, log_repo, pricing_repo = _make_service()
    log_repo.aggregate_embedding_usage.return_value = [
        EmbeddingUsageRow(
            model="text-embedding-3-small", total_tokens=1_000_000, document_count=2
        ),
    ]
    log_repo.aggregate_chat_usage.return_value = [
        ChatUsageRow(
            model="claude",
            input_tokens=1_000_000,
            output_tokens=500_000,
            reasoning_tokens=500_000,
            message_count=3,
        ),
    ]
    pricing_repo.get_price_map.return_value = {
        "text-embedding-3-small": ModelPrice(
            input_price_per_1m=0.02, output_price_per_1m=0.0, currency="USD"
        ),
        # 입력 3.0/1M, 출력 15.0/1M
        "claude": ModelPrice(
            input_price_per_1m=3.0, output_price_per_1m=15.0, currency="USD"
        ),
    }

    result = asyncio.run(service.get_user_stats(AsyncMock(), requester_id=1))

    # 임베딩: 1M 토큰 * 0.02 = 0.02
    assert result.embedding[0].cost == 0.02
    # 채팅: 입력 1M*3.0=3.0 + (출력 0.5M + 추론 0.5M)*15.0 = 15.0 → 18.0
    assert result.chat[0].total_tokens == 2_000_000
    assert result.chat[0].cost == 18.0
    # 전체 비용 = 0.02 + 18.0
    assert result.total_cost == 18.02


def test_get_user_stats_success_without_pricing_marks_cost_none():
    # 단가가 없는 모델은 cost=None이고 total_cost 합산에서 제외된다.
    service, log_repo, pricing_repo = _make_service()
    log_repo.aggregate_embedding_usage.return_value = [
        EmbeddingUsageRow(model="unpriced", total_tokens=1_000_000, document_count=1),
    ]
    log_repo.aggregate_chat_usage.return_value = []
    pricing_repo.get_price_map.return_value = {}

    result = asyncio.run(service.get_user_stats(AsyncMock(), requester_id=1))

    assert result.embedding[0].cost is None
    assert result.embedding[0].currency is None
    assert result.total_cost == 0.0


def test_get_user_stats_success_with_empty_usage():
    # 사용 이력이 없으면 빈 목록과 0 비용을 반환한다.
    service, log_repo, pricing_repo = _make_service()
    log_repo.aggregate_embedding_usage.return_value = []
    log_repo.aggregate_chat_usage.return_value = []
    pricing_repo.get_price_map.return_value = {}

    result = asyncio.run(service.get_user_stats(AsyncMock(), requester_id=1))

    assert result.embedding == []
    assert result.chat == []
    assert result.total_cost == 0.0
