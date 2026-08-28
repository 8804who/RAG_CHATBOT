import logging

from core.logging_config import _ApiCallIdLogFilter, configure_logging
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
