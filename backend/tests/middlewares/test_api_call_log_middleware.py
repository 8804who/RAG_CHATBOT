import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import Response

from core.config import config
from core.request_context import api_call_id_var
from middlewares.api_call_log_middleware import ApiCallLogMiddleware, _resolve_user_id

_LOGGER_NAME = "middlewares.api_call_log_middleware"


def _request(path: str = "/api/v1/models", cookie: str | None = None) -> Request:
    headers = []
    if cookie is not None:
        headers.append((b"cookie", cookie.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": headers,
        "query_string": b"",
    }
    return Request(scope)


def _patch_session_local(monkeypatch, auth_repository: AsyncMock) -> None:
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    session_cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(
        "middlewares.api_call_log_middleware.AsyncSessionLocal",
        MagicMock(return_value=session_cm),
    )
    monkeypatch.setattr(
        "middlewares.api_call_log_middleware.get_auth_repository",
        lambda: auth_repository,
    )


def test_resolve_user_id_success_with_valid_session(monkeypatch):
    # 유효한 세션 쿠키가 있으면 해당 user_id를 반환한다.
    auth_repository = AsyncMock()
    auth_repository.get_google_session.return_value = SimpleNamespace(user_id=7)
    _patch_session_local(monkeypatch, auth_repository)

    result = asyncio.run(
        _resolve_user_id(_request(cookie=f"{config.SESSION_COOKIE_NAME}=tok123"))
    )

    assert result == 7


def test_resolve_user_id_failed_with_no_cookie(monkeypatch):
    # 세션 쿠키가 없으면 DB 조회 없이 즉시 None을 반환한다.
    auth_repository = AsyncMock()
    _patch_session_local(monkeypatch, auth_repository)

    result = asyncio.run(_resolve_user_id(_request()))

    assert result is None
    auth_repository.get_google_session.assert_not_awaited()


def test_resolve_user_id_failed_with_expired_session(monkeypatch):
    # 세션이 만료/무효해도 예외를 내지 않고 None을 반환한다(best-effort 조회).
    auth_repository = AsyncMock()
    auth_repository.get_google_session.return_value = None
    _patch_session_local(monkeypatch, auth_repository)

    result = asyncio.run(
        _resolve_user_id(_request(cookie=f"{config.SESSION_COOKIE_NAME}=tok123"))
    )

    assert result is None


def test_dispatch_success_with_normal_call(monkeypatch, caplog):
    # 2xx 응답은 INFO 레벨로 process_status=success와 함께 기록한다.
    monkeypatch.setattr(
        "middlewares.api_call_log_middleware._resolve_user_id",
        AsyncMock(return_value=42),
    )
    middleware = ApiCallLogMiddleware(app=AsyncMock())
    call_next = AsyncMock(return_value=Response(status_code=200))

    with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        response = asyncio.run(middleware.dispatch(_request(), call_next))

    assert response.status_code == 200
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.INFO
    assert "user_id=42" in caplog.text
    assert "process_status=success" in caplog.text
    assert "status_code=200" in caplog.text


def test_dispatch_failed_with_4xx_status(monkeypatch, caplog):
    # 4xx 응답은 WARNING 레벨로 process_status=failed와 함께 기록한다.
    monkeypatch.setattr(
        "middlewares.api_call_log_middleware._resolve_user_id",
        AsyncMock(return_value=None),
    )
    middleware = ApiCallLogMiddleware(app=AsyncMock())
    call_next = AsyncMock(return_value=Response(status_code=404))

    with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        response = asyncio.run(middleware.dispatch(_request(), call_next))

    assert response.status_code == 404
    assert caplog.records[0].levelno == logging.WARNING
    assert "process_status=failed" in caplog.text
    assert "user_id=None" in caplog.text


def test_dispatch_failed_with_unhandled_exception(monkeypatch, caplog):
    # call_next가 예외를 던지면 스택트레이스와 함께 남기고 그대로 재발생시킨다
    # (등록된 예외 핸들러가 이미 처리하는 경우는 이 경로를 타지 않는다).
    monkeypatch.setattr(
        "middlewares.api_call_log_middleware._resolve_user_id",
        AsyncMock(return_value=None),
    )
    middleware = ApiCallLogMiddleware(app=AsyncMock())
    call_next = AsyncMock(side_effect=RuntimeError("boom"))

    with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        with pytest.raises(RuntimeError, match="boom"):
            asyncio.run(middleware.dispatch(_request(), call_next))

    assert caplog.records[0].levelno == logging.ERROR
    assert caplog.records[0].exc_info is not None
    assert "process_status=failed" in caplog.text


def test_dispatch_success_with_api_call_id_visible_during_call_next(monkeypatch):
    # call_next 실행 중에는 contextvar가 설정돼 있어야, 그 안에서 실행되는
    # service/repository 로그에도 core/logging_config.py 필터가 같은
    # api_call_id를 자동으로 붙일 수 있다. 응답 후에는 반드시 리셋된다.
    monkeypatch.setattr(
        "middlewares.api_call_log_middleware._resolve_user_id",
        AsyncMock(return_value=None),
    )
    middleware = ApiCallLogMiddleware(app=AsyncMock())
    seen_ids: list[str | None] = []

    async def call_next(request):
        seen_ids.append(api_call_id_var.get())
        return Response(status_code=200)

    assert api_call_id_var.get() is None
    asyncio.run(middleware.dispatch(_request(), call_next))

    assert seen_ids[0] is not None
    assert api_call_id_var.get() is None


def test_dispatch_failed_with_api_call_id_reset_after_exception(monkeypatch):
    # call_next가 예외를 던져도 contextvar는 반드시 리셋되어 다음 요청으로
    # 새어 들어가지 않는다.
    monkeypatch.setattr(
        "middlewares.api_call_log_middleware._resolve_user_id",
        AsyncMock(return_value=None),
    )
    middleware = ApiCallLogMiddleware(app=AsyncMock())
    call_next = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(middleware.dispatch(_request(), call_next))

    assert api_call_id_var.get() is None


def test_dispatch_skip_with_excluded_path(monkeypatch, caplog):
    # 헬스체크 등 제외 경로는 user_id 조회도, 로그도 남기지 않는다.
    resolve_mock = AsyncMock(return_value=1)
    monkeypatch.setattr(
        "middlewares.api_call_log_middleware._resolve_user_id", resolve_mock
    )
    middleware = ApiCallLogMiddleware(app=AsyncMock())
    call_next = AsyncMock(return_value=Response(status_code=200))

    with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        response = asyncio.run(
            middleware.dispatch(_request(path="/health"), call_next)
        )

    assert response.status_code == 200
    resolve_mock.assert_not_called()
    assert caplog.records == []
