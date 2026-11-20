import logging
import time
from datetime import UTC, datetime
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from core.config import config
from core.constants import (
    API_CALL_LOG_EXCLUDED_PATHS,
    API_CALL_STATUS_FAILED,
    API_CALL_STATUS_SUCCESS,
)
from core.request_context import api_call_id_var
from dependencies.db import AsyncSessionLocal
from dependencies.repositories import get_auth_repository

logger = logging.getLogger(__name__)


async def _resolve_user_id(request: Request) -> int | None:
    """
    세션 쿠키로 요청자 user id를 best-effort 조회

    인증 dependency(get_current_user)와 무관하게 미들웨어가 직접 세션을
    조회한다. 쿠키가 없거나 세션이 유효하지 않아도 예외를 내지 않고 None을
    반환해 공개 API 호출도 계속 로그에 남게 한다.

    Parameters:
        request(Request): 현재 요청

    Returns:
        int | None: 세션이 유효하면 user id, 아니면 None
    """
    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if not token:
        return None

    async with AsyncSessionLocal() as db:
        session = await get_auth_repository().get_google_session(
            db, token, datetime.now(UTC)
        )
        return session.user_id if session is not None else None


class ApiCallLogMiddleware(BaseHTTPMiddleware):
    """
    모든 API 호출을 구조화된 로그 한 줄로 남기는 미들웨어

    api_call_id·user_id·called_api·call_time·end_time·status_code·
    process_status를 남긴다. 헬스체크 등 인프라 경로(API_CALL_LOG_EXCLUDED_PATHS)
    는 제외한다.

    api_call_id는 응답을 반환할 때까지 core/request_context.py의 contextvar에
    저장해 둔다 — 이 요청을 처리하는 동안 service/repository에서 남기는 모든
    로그에 core/logging_config.py의 필터가 같은 id를 자동으로 붙여준다. 그래서
    이 미들웨어의 로그 메시지 자체에는 api_call_id를 중복해서 넣지 않는다.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if (
            not config.LOG_INFRA_ENDPOINTS
            and request.url.path in API_CALL_LOG_EXCLUDED_PATHS
        ):
            return await call_next(request)

        called_api = f"{request.method} {request.url.path}"
        call_time = datetime.now(UTC)
        started = time.monotonic()
        token = api_call_id_var.set(uuid4().hex)
        try:
            user_id = await _resolve_user_id(request)

            try:
                response = await call_next(request)
            except Exception:
                logger.exception(
                    "API 호출 실패: user_id=%s, api=%s, status_code=%d, "
                    "process_status=%s, call_time=%s, end_time=%s, duration_ms=%d",
                    user_id,
                    called_api,
                    HTTP_500_INTERNAL_SERVER_ERROR,
                    API_CALL_STATUS_FAILED,
                    call_time.isoformat(),
                    datetime.now(UTC).isoformat(),
                    round((time.monotonic() - started) * 1000),
                )
                raise

            process_status = (
                API_CALL_STATUS_SUCCESS
                if response.status_code < 400
                else API_CALL_STATUS_FAILED
            )
            log = logger.info if response.status_code < 400 else logger.warning
            log(
                "API 호출 완료: user_id=%s, api=%s, status_code=%d, "
                "process_status=%s, call_time=%s, end_time=%s, duration_ms=%d",
                user_id,
                called_api,
                response.status_code,
                process_status,
                call_time.isoformat(),
                datetime.now(UTC).isoformat(),
                round((time.monotonic() - started) * 1000),
            )
            return response
        finally:
            api_call_id_var.reset(token)
