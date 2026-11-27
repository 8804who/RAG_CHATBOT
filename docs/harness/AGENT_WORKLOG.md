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




### 2026-11-21 · rag-llm-engineer · T-030
- Work: eval v2 harness: `EvalCase` schema, title→document_id resolution from `document_progress_status` (unresolved/ambiguous = case error), recall/precision from citations, judge default `gpt-6.2-sol` (JUDGE_MODEL override) scoring correctness + groundedness with retrieved snippets, behavior/tool assertions (expected/forbidden tools, expectedArgs with safe arithmetic parser, maxToolCalls, no_search/web_search/not_in_docs), tool sequence per case in results, `EVAL_DATASET`, per-dataset MD table
- Files: `eval/src/{types,metrics,judge,db,api,results-reporter}.ts`, `eval/tests/rag-eval.spec.ts`, `eval/tests/metrics.unit.spec.ts` (new), `eval/README.md`, `eval/.env.example`
- Deliverables: the files above
- Verification: PM re-ran `npx tsc --noEmit` OK and `metrics.unit.spec.ts` 3/3 pass; PM confirmed `gpt-6.2-sol` is listed by /v1/models for the key. Agent-reported 2-case smoke: tool case pass, en-rag case fail (agent answered without search_documents)
- Issues found: citations = all chunks returned by search_documents that turn (agent_orchestrator.py:263), 300-char snippets; `golden-dataset.json` kept (loadtest/core/config.py reads it); maxElapsedMs/maxTotalTokens no longer asserted; unresolved-title path untested
- Follow-up: T-031 full run
- Cost: 113,439 subagent tokens, 29 tool uses, 322 s

### 2026-11-21 · rag-llm-scientist · T-029
- Work: 10 sourced source docs (5 EN, 5 KO; 2025-2026 events) + 110 eval cases in the v2 schema
- Files: `eval/test-data/v2/*.md` (10), `eval/fixtures/v2/{ko-rag,en-rag,ko-nonrag,en-nonrag,tool}.json`
- Deliverables: ko-rag 30, en-rag 30, ko-nonrag 15, en-nonrag 15, tool 20 (PM re-counted; JSON loads)
- Verification: agent-reported json.tool valid, ids unique, titles resolve, sourceUrls present. Nothing run against the live API
- Issues found: facts fetched via a summarizing WebFetch, most single-source (World Cup final, KBO MVP, Seoul mayor, vote count cross-checked); several unverifiable facts dropped (listed in report)
- Follow-up: T-031 ingest + run
- Cost: 103,708 subagent tokens, 37 tool uses, 537 s

### 2026-11-21 · rag-llm-engineer · T-031
- Work: ingested 10 v2 docs into `rag_eval_v2` (`npm run ingest:v2`, idempotent), ran full v2 baseline (110 cases, judge gpt-6.2-sol, chat gpt-4o-mini, 1 run)
- Files: `eval/scripts/ingest-v2.ts`, `eval/src/db.ts`, `eval/package.json`, `eval/tsconfig.json`, `eval/README.md`, `eval/results/2026-11-21-baseline-v2.{json,md}`
- Verification: 110/110 case records, 0 errored, 36 pass; `npx tsc --noEmit` OK; unit 3/3. PM re-ran tsc + unit before PR #7
- Issues found: only 24/60 RAG cases call search_documents (rest tavily) → P20; 8 nonrag forbidden tavily, 3 over maxToolCalls → P21; 2 calc arg errors → P22; precision ceiling ~1/7 on 15-chunk collection → P23 (threshold decision open)
- Follow-up: 2 more v2 runs for variance; A1 force-search experiment
- Shipped: PR #7 (harness), PR #8 (baselines), docs PR (plan + harness docs)

### 2026-11-26 · frontend-developer + frontend-code-reviewer · T-032
- Work: D-015 recorded, `.claude/.rules/design.md` points at `.claude/design/DESIGN-spotify.md`; whole SPA re-themed dark (semantic `@theme` tokens, `btn-*`/`field` utilities in `index.css`, className-only changes in 19 files)
- Files: `frontend/src/**`, `docs/harness/DESIGN_GUIDELINES.md`, `.claude/.rules/design.md`, `docs/harness/DECISION_LOG.md`
- Verification: build + lint OK (developer, reviewer, and main session re-run); Playwright screenshots against mocked API, backend not running
- Review: CR-011 PASS_WITH_NOTES; KI-030 (drop-zone border contrast) fixed by main session
- Follow-up: unused `StatusBadge.tsx`; sidebar not collapsing on mobile; sub-44px touch targets (pre-existing)

### 2026-11-26 · main session (user-directed) · T-033
- Work: multi-turn memory via LangGraph `AsyncPostgresSaver` (thread_id=chat_id) + `SummarizationMiddleware`; Alembic excludes checkpoint tables
- Files: backend/app/services/agent/agent_orchestrator.py, dependencies/clients.py, dependencies/services.py, main.py, core/constants.py, migrations/env.py, pyproject.toml, uv.lock, tests/services/agent/test_agent_orchestrator.py, docs/ARCHITECTURE.md
- Verification: `uv run pytest -c pyproject.toml -q` → 102 passed / 2 failed (stale warmup tests, removed in T-038); live 2-turn round-trip on real AsyncPostgresSaver (no LLM) OK; `alembic check` → no new operations
- Issues found: CR-012 F1 (failed turn leaves dangling tool_calls) — fixed in T-038
- Follow-up: E2E in T-041
- Cost: n/a (main session)

### 2026-11-26 · backend-code-reviewer · T-034
- Work: full backend review incl. T-033 → CR-012 CHANGES_REQUESTED (F1 blocker, F2 major, F3–F9 minor)
- Deliverables: CR-012, KI-031..039
- Verification: pytest 102 passed / 2 failed (stale tests); no EXPLAIN (postgres MCP down)
- Issues found: KI-031..039
- Follow-up: T-038
- Cost: 102256 tokens / 12 tool uses / 131.8s

### 2026-11-26 · frontend-code-reviewer · T-035
- Work: full frontend review → CR-013 CHANGES_REQUESTED (F1 blocker invalidate loop, F2–F6 major, F7–F14 minor)
- Deliverables: CR-013, KI-040..042
- Verification: `npm run build` OK, `npm run lint` clean; code tracing, no browser run
- Issues found: KI-040..042
- Follow-up: T-039, T-040
- Cost: 74162 tokens / 7 tool uses / 66.4s

### 2026-11-26 · system-architect · T-036
- Work: architecture review LLM ↔ backend ↔ frontend; 9 ranked findings; SYSTEM_ARCHITECTURE.md synced incl. T-033; D-016 proposed
- Files: docs/harness/SYSTEM_ARCHITECTURE.md, docs/harness/DECISION_LOG.md
- Verification: code reading only; nothing run
- Issues found: failed-turn thread corruption, shared session in parallel tools, KI-010 pool exhaustion, unpruned checkpoints, concurrent-send race, unused max_tokens, summarization cost, no history endpoint
- Follow-up: D-016 accepted by PM with Redis-lock amendment; fixes in T-038/T-040
- Cost: 119740 tokens / 17 tool uses / 154.7s

### 2026-11-26 · ux-designer · T-037
- Work: UX audit of the SPA → 17 findings (P0×3, P1×7, P2×7)
- Verification: code-only audit, no Playwright run
- Issues found: in report (no owned docs)
- Follow-up: T-039, T-040
- Cost: 53314 tokens / 4 tool uses / 30.8s

### 2026-11-26 · backend-developer + backend-code-reviewer · T-038
- Work: D-016 all-or-nothing turn (thread rollback incl. cancellation, shielded), Redis per-chat lock → 409, per-tool DB sessions, aprune keep_latest, ChatOpenAI max_tokens/timeout/max_retries, summarization 30k trigger on gpt-4o-mini with usage callback, `GET /chats/{id}/messages`, stale tests removed, INFO logs without args/email, conninfo via make_conninfo, lifespan AsyncExitStack
- Files: backend/app/** (agent_orchestrator.py, tools.py, chat_repository.py, chats.py, responses.py, exceptions/chat.py, redis_client.py, dependencies/*, chat_model_config.py, main.py, core/constants.py), backend/tests/**, docs/harness/API_CONTRACTS.md, docs/ARCHITECTURE.md
- Verification: developer + PM: `uv run pytest -c pyproject.toml -q` → 125 passed, then 129 passed / 0 failed after CR-014 revision; ruff check + format --check clean
- Review: CR-014 PASS_WITH_NOTES (F1 cancel-path rollback, F6 lifespan → fixed with tests, PM sign-off per reviewer)
- Issues found: KI-043..051 (minor/deferred)
- Follow-up: T-041 E2E
- Cost: dev 186147 tokens / 38 tool uses / 545.8s + revision 194814 / 5 / 70.7s; reviewer 100324 / 17 / 149.0s

### 2026-11-26 · frontend-developer + frontend-code-reviewer · T-039, T-040
- Work: T-039 non-chat fixes (status-query loop, per-file uploads, per-row delete + InlineConfirm, logout cache clear, apiFetch headers/detail, .md/.txt only, mobile drawer, 44px targets, named exports, safeHttpUrl); T-040 chat (URL chat id + history hydration, error/Retry/409, abort on New chat, ThinkingIndicator, IME-safe Enter, safe citations); CR-015 follow-ups (id fallback, stable history ids, no navigate after unmount, no cache write after logout, poll retry, InlineConfirm focus/color, drawer label)
- Files: frontend/src/**, docs/harness/DESIGN_GUIDELINES.md
- Verification: developer + PM: `npm run build` OK, `npm run lint` clean, 0 `export default`; developer Playwright with stubbed API (backend down); follow-ups not browser-checked
- Review: CR-015 PASS_WITH_NOTES; PM sign-off per reviewer
- Issues found: KI-052..056; open: global 401 (CR-013 F10), drawer focus trap
- Follow-up: T-041 E2E
- Cost: T-039 149347 tokens / 29 / 333.6s; T-040 119734 / 24 / 291.1s + follow-up 145086 / 32 / 92.1s; reviewer 97341 / 9 / 131.0s

### 2026-11-27 · qa-engineer · T-041
- Work: E2E on real API + real OpenAI with test session bypass. QA-002: 8 PASS, 1 PARTIAL (failed turn forced only pre-LLM), KI-057 critical (Redis password not passed → every send 500 on stock Redis). QA-003 re-check on stock Redis: 5/5 PASS
- Deliverables: QA-002, QA-003, KI-057..059, screenshots `.playwright-mcp/qa00{2,3}-*.png`
- Verification: Playwright MCP exploratory (no spec file); 11 + 3 billed turns; turn latency 1.0–9.7 s; cleanup re-queried to 0 rows
- Issues found: KI-057 (closed), KI-058 (closed), KI-059 (partly closed: empty chat row after failed first turn, orphan progress rows)
- Follow-up: none for this scope
- Cost: QA-002 118068 tokens / 69 tool uses / 427.9s; QA-003 125655 tokens / 76 tool uses / 585.9s (as reported for the resumed run)

### 2026-11-27 · backend-developer + frontend-developer · T-038, T-040 (QA revisions)
- Work: BE: Redis password passed, generic English chat error messages without ids (KI-057, KI-058). FE: draft restored after failed send, input hidden on unavailable chat, fixed English error copy per status (KI-058/059)
- Verification: PM re-run `uv run pytest -c pyproject.toml -q` → 131 passed / 0 failed, ruff clean, live ping to stock Redis OK; `npm run build` + `npm run lint` OK; QA-003 PASS
- Cost: BE 201183 tokens / 6 / 47.6s; FE 156501 / 6 / 67.9s

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
