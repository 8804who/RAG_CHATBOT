import logging

import pytest

from core.config import config
from core.logging_config import (
    _ApiCallIdLogFilter,
    _InfraEndpointAccessLogFilter,
    configure_logging,
)
from core.request_context import api_call_id_var


def _record() -> logging.LogRecord:
    return logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )


def test_filter_success_with_api_call_id_set():
    # 현재 요청의 api_call_id가 contextvar에 있으면 레코드에 그대로 주입한다.
    token = api_call_id_var.set("abc123")
    try:
        record = _record()
        result = _ApiCallIdLogFilter().filter(record)
    finally:
        api_call_id_var.reset(token)

    assert result is True
    assert record.api_call_id == "abc123"


def test_filter_success_with_no_api_call_id():
    # 요청 컨텍스트 밖(워커, 시작 로그 등)에서는 "-"로 표시한다.
    record = _record()

    result = _ApiCallIdLogFilter().filter(record)

    assert result is True
    assert record.api_call_id == "-"


def test_configure_logging_success_with_repeated_calls():
    # root logger에 핸들러 1개 + 상관관계 필터가 등록되고, 반복 호출해도
    # 핸들러가 누적되지 않는다(진입점에서 실수로 두 번 호출해도 안전해야 함).
    configure_logging()
    configure_logging()

    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert any(
        isinstance(log_filter, _ApiCallIdLogFilter)
        for log_filter in root.handlers[0].filters
    )


def _access_record(path: str) -> logging.LogRecord:
    # uvicorn.access 레코드 args: (client_addr, method, full_path, http_version, status)
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:5000", "GET", path, "1.1", 200),
        exc_info=None,
    )


@pytest.mark.parametrize("path", ["/health", "/metrics", "/metrics?x=1"])
def test_infra_filter_failed_with_infra_path(monkeypatch, path):
    """
    인프라 경로 access 로그 차단(실패=드롭)

    입력 데이터
        - LOG_INFRA_ENDPOINTS = False, 경로 /health, /metrics(쿼리스트링 포함)

    예상 출력 데이터
        - filter()가 False를 반환해 로그가 출력되지 않음
    """
    monkeypatch.setattr(config, "LOG_INFRA_ENDPOINTS", False)

    assert _InfraEndpointAccessLogFilter().filter(_access_record(path)) is False


def test_infra_filter_success_with_api_path(monkeypatch):
    """
    일반 API 경로 access 로그 통과(성공)

    입력 데이터
        - LOG_INFRA_ENDPOINTS = False, 경로 /api/v1/models

    예상 출력 데이터
        - filter()가 True를 반환
    """
    monkeypatch.setattr(config, "LOG_INFRA_ENDPOINTS", False)

    assert _InfraEndpointAccessLogFilter().filter(_access_record("/api/v1/models"))


def test_infra_filter_success_with_logging_enabled(monkeypatch):
    """
    환경 변수로 인프라 경로 로그 노출(성공)

    입력 데이터
        - LOG_INFRA_ENDPOINTS = True, 경로 /health

    예상 출력 데이터
        - filter()가 True를 반환
    """
    monkeypatch.setattr(config, "LOG_INFRA_ENDPOINTS", True)

    assert _InfraEndpointAccessLogFilter().filter(_access_record("/health"))


def test_configure_logging_success_with_access_filter_attached():
    """
    uvicorn access 로거 필터 등록(성공)

    입력 데이터
        - configure_logging() 2회 호출

    예상 출력 데이터
        - uvicorn.access 로거에 인프라 경로 필터가 정확히 1개 등록
    """
    configure_logging()
    configure_logging()

    access_filters = logging.getLogger("uvicorn.access").filters
    assert (
        sum(isinstance(f, _InfraEndpointAccessLogFilter) for f in access_filters) == 1
    )
