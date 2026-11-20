import logging

from core.config import config
from core.constants import API_CALL_LOG_EXCLUDED_PATHS, UVICORN_ACCESS_LOGGER
from core.request_context import api_call_id_var


class _ApiCallIdLogFilter(logging.Filter):
    """
    현재 요청의 api_call_id를 모든 로그 레코드에 주입하는 필터

    어느 계층(service/repository/worker)에서 로그를 남기든 코드 변경 없이
    현재 요청의 api_call_id가 자동으로 붙는다. 요청 컨텍스트 밖(워커, 시작
    로그 등)에서는 "-"로 표시한다.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.api_call_id = api_call_id_var.get() or "-"
        return True


class _InfraEndpointAccessLogFilter(logging.Filter):
    """
    uvicorn access 로그에서 인프라 경로(헬스체크·메트릭 등) 요청을 걸러내는 필터

    LOG_INFRA_ENDPOINTS가 False면 API_CALL_LOG_EXCLUDED_PATHS 요청 로그를 버리고,
    True면 모든 요청 로그를 통과시킨다.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if config.LOG_INFRA_ENDPOINTS:
            return True
        # uvicorn access 레코드 args: (client_addr, method, full_path, http_version, status)
        full_path = str(record.args[2]) if len(record.args or ()) > 2 else ""
        return full_path.split("?", 1)[0] not in API_CALL_LOG_EXCLUDED_PATHS


def _attach_access_log_filter() -> None:
    """
    uvicorn access 로거에 인프라 경로 필터 등록(중복 등록 방지)
    """
    access_logger = logging.getLogger(UVICORN_ACCESS_LOGGER)
    if not any(
        isinstance(log_filter, _InfraEndpointAccessLogFilter)
        for log_filter in access_logger.filters
    ):
        access_logger.addFilter(_InfraEndpointAccessLogFilter())


def configure_logging() -> None:
    """
    애플리케이션 전역 로깅 설정(레벨·포맷 지정 + api_call_id 상관관계 필터 적용)

    root logger를 설정하지 않으면 기본 레벨(WARNING)로 인해 INFO/DEBUG
    로그가 전부 소실되므로, API 서버·워커 등 모든 진입점에서 시작 시
    반드시 호출해야 한다.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s [api_call_id=%(api_call_id)s]:"
            " %(message)s"
        )
    )
    handler.addFilter(_ApiCallIdLogFilter())

    root = logging.getLogger()
    root.setLevel(config.LOG_LEVEL)
    root.handlers = [handler]
    _attach_access_log_filter()
