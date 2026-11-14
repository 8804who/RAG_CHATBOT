# Logging rules in "backend/"

## Basics
- No `print()`; use only the standard library `logging` module (no third-party logging libraries)
- Declare `logger = logging.getLogger(__name__)` at the top of each module
- Don't build messages with f-strings; use lazy `%s`/`%d` formatting (so formatting is skipped entirely when the level is off)
- Never log sensitive data: passwords, access tokens, session cookies, API keys

## Logger setup (required in every entrypoint)
- The API server (`main.py`) and every worker entrypoint (`workers/*.py`) must call `configure_logging()` from `core/logging_config.py` at startup
- Without it the root logger stays at the default level (`WARNING`) and every `INFO`/`DEBUG` log is lost (with no handler, only `WARNING` and above reach the last-resort output) — check this whenever you add a new entrypoint
- The level is controlled by the `config.LOG_LEVEL` env var (default `INFO`)
- The log format prefixes every record with `[api_call_id=...]` (`%(asctime)s %(levelname)s %(name)s [api_call_id=%(api_call_id)s]: %(message)s`) — see "Request correlation" below. Don't call `logging.basicConfig()` or create new handlers yourself; configure only through `configure_logging()` (so this filter is always attached)

## Request correlation (api_call_id) — automatically included in logs from every layer (required)
- We must be able to trace which API call raised an error and what data it handled. So **any log from any layer — service, repository, worker — automatically carries the api_call_id current at that moment**: `ApiCallLogMiddleware` stores a new id per request in `core/request_context.py::api_call_id_var` (a contextvar), and `_ApiCallIdLogFilter` in `core/logging_config.py` injects it into every log record
- **Service/repository code never handles the api_call_id directly or puts it in log messages** — just log as usual with `logging.getLogger(__name__)` and the formatter adds it. Don't pass it as a function argument or splice it into message strings (that adds plumbing across layer boundaries and duplicates what the filter already does)
- Instead, **"what data did this request handle" must still be logged as key=value in each log** (e.g. `chat_id=%s`, `document_id=%s`, `collection_name=%s`) — the api_call_id finds "which request", and the domain fields of that request's logs reconstruct "what it was doing with which data when it failed". One `grep api_call_id=<id>` should connect a request's whole flow, from the middleware request/response log to the service-layer start/complete/fail logs
- Logs from workers with no HTTP request (Kafka consumers) always show api_call_id as `"-"` — workers keep using their own correlation keys such as `document_id` (no extra work needed)

## Choosing a level
- `DEBUG`: detailed progress inside one request (e.g. number of chunks retrieved, token usage) — assume it's invisible at the production default level
- `INFO`: start/complete of one business flow (e.g. upload accepted, chat created, message processed)
- `WARNING`: failures recoverable by retry, partial success
- `ERROR`/`logger.exception`: final failure, a user request that couldn't be completed — inside an `except` block, use `logger.exception` instead of `logger.error` when you need the stack trace

## Message format — two kinds
### Business event logs (normal flow, INFO/DEBUG/WARNING)
- A short Korean phrase ending in a verb/noun form, followed by context values as `key=%s`
- Use the patterns "{동작} 시작: ...", "{동작} 완료: ...", "{동작} 실패: ..."

```python
logger.info(
    "채팅 생성 완료: chat_id=%s, collection=%s, chat_model=%s, owner_id=%s",
    chat.id,
    collection_name,
    chat_model,
    owner_id,
)
```

### Exception/error logs
- When raising an `AppException`, use `code_path` in the form `"{모듈}-{함수명}-error"` (`exceptions/base.py`) — the global exception handler (`exceptions/handler.py::app_exception_handler`) logs this value as is, so service code doesn't need to log again for exceptions that go straight to the user
- The global handler sends `AppException.message` to the client as the response `detail`. Don't put internal details in it (queries, stacks, keys, internal IDs); keep those in logs only
- However, when one operation spans several steps (e.g. search → generate) and you need to tell which step failed, or when the exception doesn't reach a user response (e.g. a worker retry loop), log the context inside `try/except` with `logger.exception("{동작} 실패: key=%s, ...")` and then re-raise with `raise` (never swallow the exception)

```python
try:
    chunks = await self._retrieval.retrieve(db, chat.collection_name, query)
    answer = await self._generation.answer(chat.chat_model, query, chunks)
except Exception:
    logger.exception(
        "메시지 처리 실패: chat_id=%s, requester=%s",
        chat_id,
        requester.email,
    )
    raise
```

## Where to log (layer rules)
- Log only in the **service layer** (which knows the business flow) and in **worker entrypoints**
- **The repository/client layers don't log** — raise typed custom exceptions instead, so the service handles them or the global handler records them via `code_path` (exception: explicit best-effort behavior that swallows failures and only warns, like `ensure_topics` in `clients/kafka_client.py`, may use `logger.warning` in the client layer)
- Endpoints don't log directly (they have no business logic) — they only turn the service result into a response
- Exception: **cross-cutting middleware** wrapping HTTP requests/responses (`middlewares/*.py`) may log things common to every endpoint (e.g. the API call log), because that's an infrastructure concern, not one endpoint's business logic

## API call log (middleware)
- `middlewares/api_call_log_middleware.py::ApiCallLogMiddleware` logs every API call as one line (not stored in Postgres — audit/aggregate logs that belong in the DB use the existing `LogRepository`/`DocumentManageLog`/`ChatUsageLog` patterns separately)
- Fields: `api_call_id` (uuid4 hex, one call's id — included automatically via the `[api_call_id=...]` prefix of the log format, not the message body, so the middleware doesn't pass it again as a message argument), `user_id` (best-effort lookup from the session cookie; `None` for anonymous requests), `api` (`"{METHOD} {path}"`), `status_code`, `process_status` (`API_CALL_STATUS_SUCCESS`/`API_CALL_STATUS_FAILED`, `core/constants.py`, based on `status_code < 400`), `call_time`/`end_time` (ISO 8601, UTC), `duration_ms`
- 4xx/5xx use `logger.warning`; 2xx/3xx use `logger.info`. Only in the very rare case where `call_next()` itself raises (before a registered exception handler handles it), log with `logger.exception` and re-raise
- Exclude non-user paths such as health checks by adding them to `API_CALL_LOG_EXCLUDED_PATHS` in `core/constants.py`
- Update this list whenever you add a new infrastructure path (e.g. a metrics endpoint)

## Don't
- Use `print()`
- Build log messages with f-strings
- Catch an exception, log it, and swallow it (unless it's intentional retry/best-effort handling, always `raise`)
- Add business event logs in the repository/client layers
- Log personal data, credentials, or whole request bodies as is
