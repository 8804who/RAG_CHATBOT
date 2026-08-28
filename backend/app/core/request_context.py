from contextvars import ContextVar

# 현재 요청의 API 호출 id(ApiCallLogMiddleware가 설정). 서비스/레포지토리
# 코드는 이 값을 직접 다루지 않는다 — core/logging_config.py의 로그 필터가
# 모든 로그 레코드에 자동으로 주입한다.
api_call_id_var: ContextVar[str | None] = ContextVar("api_call_id", default=None)
