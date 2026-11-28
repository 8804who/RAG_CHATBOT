# Agent Worklog

> Owner: `pm` only ([HANDOFF_PROTOCOL.md §2](HANDOFF_PROTOCOL.md#2-document-ownership-matrix)). `pm` appends one entry per agent report, at the **end** (append-only; never edit earlier entries).
> Format: [HANDOFF_PROTOCOL.md §4](HANDOFF_PROTOCOL.md#agent_worklog-entry-format). Verification that didn't run is written as "not run". Entries of `COMPLETED` tasks move to `archive/` via `archive_logs.py`.

## Records

### 2026-11-14 · main-session · T-001
- Work: built the multi-agent harness — created 14 docs in `docs/harness/`, added the Harness section to `CLAUDE.md`, added harness references and doc ownership to the 10 agents in `.claude/agents/`, moved PM management docs from `docs/pm/` to `docs/harness/` (D-009)
- Files: `docs/harness/*.md` (14 new), `CLAUDE.md`, `.claude/agents/*.md` (10)
- Deliverables: the docs above
- Verification: a script checked that internal doc links resolve, agent names match files, and every agent file references the harness. Protocol compliance in a real agent run: not run.
- Issues found: KI-005, KI-006, KI-007
- Follow-up: KI-006 needs a user decision / check that PM follows the protocol on the first real task

### 2026-11-14 · frontend-developer · T-012
- Work: non-root frontend container (node 24 build → nginx-unprivileged uid 101 :8080, /api/ → api:8000 proxy, SPA fallback, cache headers, client_max_body_size 50m as an estimate)
- Files: `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/.dockerignore`
- Deliverables: the files above
- Verification: `npm run build` passed (as reported). `docker build` not run (Docker daemon down)
- Issues found: nginx resolves `api` at startup → compose depends_on needed; `export default` rule violations in `UploadZone.tsx` and `DocumentUpload.tsx` (pre-existing code)
- Follow-up: T-014 review; the compose `frontend` service is in T-011 (blocked at the time)

### 2026-11-14 · frontend-developer · T-021
- Work: KI-018 fix — resolver 127.0.0.11 + `proxy_pass $api_upstream$request_uri`
- Files: `frontend/nginx.conf`
- Deliverables: the file above
- Verification: `npm run build` passed (as reported). `nginx -t` and runtime not run
- Issues found: none
- Follow-up: T-023 review

### 2026-11-14 · backend-developer · T-020
- Work: compose split (system: infra, `name: rag_chatbot` / service: api, frontend, ingest-worker, external network), non-root backend image (uid 10001), added `LOG_INFRA_ENDPOINTS=false` to `.env`, updated doc references
- Files: `backend/app/WorkerImage.Dockerfile`, `system-docker-compose.yaml` (git mv), `service-docker-compose.yaml` (new), `monitoring-docker-compose.yaml` (header), `backend/app/.env`, `CLAUDE.md`, `loadtest/README.md`, `eval/README.md`, `docs/ARCHITECTURE.md`, `docs/KAFKA_INGESTION.md`, `docs/EMBEDDING_AND_COLLECTIONS.md`, `docs/RAG_ARCHITECTURE.md`
- Deliverables: the files above
- Verification: all three compose configs exit 0 (PM re-ran), volume and network names checked, stale-reference grep 0 hits. Image build not run
- Issues found: orphaned volume rag_chatbot_fastembed_cache; backend `.dockerignore` doesn't exclude `.cache/`
- Follow-up: T-022 review

### 2026-11-14 · backend-developer · T-020 (revision: user request + CR-009)
- Work: infra project named `rag_chatbot_system`; service and monitoring external network `rag_chatbot_system_default`; `compileall` added to the Dockerfile
- Files: `system-docker-compose.yaml`, `service-docker-compose.yaml`, `monitoring-docker-compose.yaml`, `backend/app/WorkerImage.Dockerfile`, `docs/ARCHITECTURE.md`
- Deliverables: the files above
- Verification: all three compose configs exit 0, stale network references 0 (PM re-ran). Image build not run
- Issues found: none
- Follow-up: T-024 review




### 2026-11-27 · frontend-developer · T-043
- Did: `listChats`/`deleteChat` in `lib/api/chat.ts`, types in `lib/types.ts`; `useChatList`/`useDeleteChat` in `hooks/useChat.ts` (key `['chats','list']`, invalidated after create + each successful send); new `components/chat/ChatListPanel.tsx`, `ChatListItem.tsx`; ChatPage list (lg column, overlay below lg), New chat, `aria-current`, delete via `InlineConfirm`, 409 message.
- Verification: `npm run build` OK, `npm run lint` OK (dev, after `npm ci`; PM re-run OK). No browser check, no tests (no FE runner).
- Open: browser check against real T-042 backend.
- Cost: 60354 tokens, 14 tool uses, 203 s

### 2026-11-27 · frontend-code-reviewer · T-043
- Did: reviewed the T-043 frontend diff → CR-016 PASS_WITH_NOTES: 1 major a11y (overlay focus/Escape/inert), 2 minor (stale activeChatId in delete onSuccess, missing hook return types), 1 cost note (no action).
- Verification: code review only; relied on the PM build+lint run; no browser pass.
- Cost: 42571 tokens, 5 tool uses, 47 s

### 2026-11-27 · frontend-developer · T-043 (revision)
- Did: CR-016 notes 1–3. Overlay reuses the Layout drawer pattern: focus to close button, document Escape, role=dialog/aria-modal only while open, main `inert`, focus returns to the Chats button on every close path. `useDeleteChat` checks the current chat id at success. Explicit hook return types.
- Verification: build + lint OK (dev; PM re-run OK). No browser check.
- Open: widening past lg with the overlay open leaves main inert until Escape.
- Cost: 43781 tokens, 5 tool uses, 55 s

### 2026-11-27 · frontend-code-reviewer · T-043 (re-review)
- Did: verified the CR-016 notes 1–3 fixes by code trace → PASS_WITH_NOTES, no blockers. The lg-resize inert edge is non-blocking (cheapest fix: a matchMedia change listener calls closeList).
- Verification: code trace only; no browser; relied on the PM build+lint run.
- Cost: 37482 tokens, 3 tool uses, 16 s

### 2026-11-27 · backend-developer · T-042
- Did: `GET /api/v1/chats` as one statement (LATERAL max(created_at) + correlated first-user-message title, coalesce ordering, LIMIT `CHAT_LIST_LIMIT`=100 with a ponytail comment); `DELETE /api/v1/chats/{id}` → 204: owner check, Redis turn lock (new `_acquire_turn_lock`, shared with send_message), `adelete_thread`, then delete the row. `ChatSummary` DTO, `ChatSummaryResponse`/`ChatListResponse`. API_CONTRACTS rows added. No migration.
- Verification: TDD (+5 repo, +8 service, +7 endpoint tests); pytest 151 passed / 0 failed; ruff check+format clean (dev and PM re-run, dummy env vars). SQL not run against live Postgres (docker down).
- Open: orphan `chat_usage_logs`/`agent_tool_call_logs` rows (conversation_id has no FK) stay after delete and keep counting toward usage; live SQL/EXPLAIN check.
- Cost: 95839 tokens, 36 tool uses, 436 s

### 2026-11-27 · backend-code-reviewer · T-042
- Did: reviewed the T-042 backend diff → CR-017 PASS_WITH_NOTES, no blockers. F1 send/delete race (ownership not re-checked after the lock), F2 read txn open across the lock, F3 title subquery may run per row (needs EXPLAIN), test gaps (no live-Postgres test). Orphan usage/tool-log rows acceptable for now.
- Verification: code review only; no live SQL (docker down); relied on the PM pytest/ruff run.
- Cost: 49467 tokens, 6 tool uses, 42 s

### 2026-11-27 · backend-developer · T-042 (revision)
- Did: CR-017 F1/F2. send_message and delete_chat re-check `_get_owned_chat` inside the turn lock (404 instead of an LLM turn plus an FK 500); delete_chat commits its read txn before taking the lock. +3 orchestrator tests (each failed first).
- Verification: pytest 154 passed / 0 failed; ruff check + format clean (dev and PM re-run, dummy env).
- Cost: 48468 tokens, 10 tool uses, 88 s

### 2026-11-27 · backend-code-reviewer · T-042 (re-review)
- Did: CR-017 re-review addendum → PASS. F1/F2 closed, the lock is released on every path, send_message unchanged otherwise. Gap: no test that `_run_turn` gets the re-fetched chat.
- Verification: code read only; relied on the PM pytest/ruff run.
- Cost: 37918 tokens, 4 tool uses, 16 s

### 2026-11-28 · system-architect · T-045
- Work: approved PM's SSE streaming contract with amendments (lock owned/released by the stream generator, TTL ceiling if client drops before first chunk; explicit `stream_usage=True` on ChatOpenAI); recorded D-018
- Files: `docs/harness/DECISION_LOG.md` (D-018), `docs/harness/API_CONTRACTS.md` (endpoint row, SSE note, change history)
- Deliverables: D-018 (PM accepted 2026-11-28)
- Verification: docs only; checked installed FastAPI 0.136.3 / Starlette 1.3.0 / uvicorn source for session lifetime and disconnect handling (as reported). No tests run
- Issues found: streamed calls log status 200 and header-time duration in ApiCallLogMiddleware (known limit in D-018)
- Follow-up: T-046 must test disconnect → rollback through the real middleware stack
- Cost: 55606 tokens / 13 tool uses / 145s

### 2026-11-28 · frontend-developer · T-048
- Work: token-by-token chat answers via fetch+ReadableStream SSE parser; `streamMessage` replaces unused `sendMessage`; streaming bubble reuses MessageBubble, ThinkingIndicator until first token; `aria-busy` while streaming; nginx `proxy_buffering off`
- Files: `frontend/src/lib/api/{client.ts,sse.ts(new),chat.ts}`, `frontend/src/lib/types.ts`, `frontend/src/hooks/useChat.ts`, `frontend/src/pages/ChatPage.tsx`, `frontend/nginx.conf`, `docs/ARCHITECTURE.md:56`
- Deliverables: code above
- Verification: `npm run build` pass, `npm run lint` 0 errors (as reported; PM re-ran both: pass). Throwaway node check of the parser/streamMessage in scratchpad (not in repo). Browser check not run (backend endpoint not up)
- Issues found: `docs/ARCHITECTURE.md:9` still says non-streaming (left to T-046 doc update)
- Follow-up: T-049 review
- Cost: 62020 tokens / 16 tool uses / 152s

### 2026-11-28 · frontend-developer · T-048 (revision CR-019)
- Work: F1 in-flight question/streaming answer use the cache ids (`chatMessageId(chatId, n/n+1)`), no remount on done; F4 removed `proxy_buffering off` (backend `X-Accel-Buffering: no` covers it), comment kept
- Files: `frontend/src/hooks/useChat.ts:139-160`, `frontend/nginx.conf:17`
- Deliverables: code above
- Verification: `npm run build` OK, `npm run lint` clean (as reported; PM re-ran: pass). Browser not run
- Issues found: new-chat case switches ids once at createChat, before any token (accepted)
- Follow-up: T-049 re-review
- Cost: 36935 tokens / 6 tool uses / 31s

### 2026-11-28 · backend-developer · T-046
- Work: `POST /chats/{id}/messages/stream` SSE (token/done/error), pre-stream JSON 4xx, generator-owned lock, shared `_start_turn`/`_finish_turn` with the non-streaming path, close-stream-then-rollback on error/cancel, explicit `stream_usage=True`
- Files: `backend/app/services/agent/agent_orchestrator.py`, `api/v1/endpoints/chats.py`, `core/constants.py`, `schemes/dto/chat.py`, `core/model_config/chat_model_config.py`, `exceptions/handler.py`; tests in `tests/services/agent/test_agent_orchestrator.py`, `tests/api/v1/endpoints/test_chats.py`, `tests/core/model_config/test_chat_model_config.py`; `docs/ARCHITECTURE.md:9,23`, `docs/harness/SYSTEM_ARCHITECTURE.md:49`
- Deliverables: code + 21 new tests
- Verification: `uv run pytest` 175 passed, 1 warning; ruff check + format --check clean (as reported; PM re-ran with dummy env: 175 passed, ruff clean). Disconnect test runs through the real ASGI app + middleware. Live LLM stream not run
- Issues found: timeout is per-await deadline (deviation); pre-tool text streams then is replaced by done; post-persistence usage-log failure → client gets error but messages saved (same gap as non-streaming, KI-044); `CLAUDE.md:3` says non-streaming
- Follow-up: T-047 review; PM fixes CLAUDE.md line
- Cost: 148160 tokens / 44 tool uses / 857s

### 2026-11-28 · backend-developer · T-046 (revision CR-020)
- Work: `_shielded` wraps `asyncio.shield` in `anyio.CancelScope(shield=True)` (covers Starlette's re-firing cancel scope); stream lock release goes through `_shielded`; disconnect logs WARNING without traceback
- Files: `backend/app/services/agent/agent_orchestrator.py:457,551,787`; tests `tests/services/agent/test_agent_orchestrator.py:1658` (new, anyio task-group cancel), `tests/api/v1/endpoints/test_chats.py:444` (spec_version 2.3, awaiting cleanup)
- Deliverables: code + tests
- Verification: both tests failed before the fix (assert / TimeoutError), pass after; `uv run pytest` 176 passed; ruff clean (as reported; PM re-ran: 176 passed, ruff clean)
- Issues found: `anyio` imported directly but only a transitive dep (not in pyproject); `send_message`/`delete_chat` unlocks unshielded (out of scope)
- Follow-up: T-047 re-review
- Cost: 64465 tokens / 17 tool uses / 163s

### 2026-11-28 · pm · T-050
- Work: QA E2E not run: VERIFY_BLOCKED (no .env in worktree, :8000 held by the user's own debugger process, Google OAuth login required)
- Files: `docs/harness/TASK_BOARD.md`, `docs/harness/KNOWN_ISSUES.md` (KI-060, KI-061), `CLAUDE.md:3`, `docs/harness/PROJECT_CONTEXT.md:56`, `docs/harness/LLM_SPECIFICATION.md:21` (non-streaming → D-018 fact; LLM_SPECIFICATION is rag-llm-owned, one-line fact fix by PM)
- Deliverables: board/doc updates
- Verification: not run (env blocker)
- Issues found: KI-060, KI-061
- Follow-up: user runs the live smoke steps
- Cost: n/a
