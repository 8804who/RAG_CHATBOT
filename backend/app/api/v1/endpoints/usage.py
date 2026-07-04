from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.auth import get_current_user
from dependencies.db import get_db_session
from dependencies.services import get_usage_stats_service
from models import User
from schemes.responses import UsageStatsResponse
from services.usage import UsageStatsService

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/stats", response_model=UsageStatsResponse)
async def get_my_usage_stats(
    usage_service: UsageStatsService = Depends(get_usage_stats_service),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> UsageStatsResponse:
    """
    ### 내 토큰 사용량/비용 통계 조회(마이페이지)

    모델별로 그룹핑된 임베딩(인제스트)·채팅 토큰 사용량과, 토큰×단가로 계산한
    비용을 반환한다. 단가가 등록되지 않은 모델은 cost=null.

    Response Body:
        embedding: 모델별 임베딩 사용량
            model, total_tokens, document_count, cost, currency
        chat: 모델별 채팅 사용량
            model, input_tokens, output_tokens, reasoning_tokens,
            total_tokens, message_count, cost, currency
        total_cost: 전체 비용 합계
        currency: 통화(기본 USD)
    """
    return await usage_service.get_user_stats(db, current_user.id)
