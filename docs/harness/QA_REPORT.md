# QA Report

> Owner: `qa-engineer` · append-only (new test runs go at the end). Record only tests that actually ran.
> E2E tests live in `eval/tests/e2e/` (Playwright, a separate project in `eval/playwright.config.ts`). RAG quality eval: [LLM_SPECIFICATION.md](LLM_SPECIFICATION.md#evaluation-and-performance-criteria).
> Add failures to [KNOWN_ISSUES.md](KNOWN_ISSUES.md) and put the verdict in your report; `pm` moves the [TASK_BOARD.md](TASK_BOARD.md) row to `REVISION_REQUIRED` ([HANDOFF_PROTOCOL.md §2](HANDOFF_PROTOCOL.md#2-document-ownership-matrix)).

## Format

```markdown
### QA-xxx · YYYY-MM-DD · <Task ID / feature>
- Environment: what was running (infra/backend/workers/frontend), browser and viewport
- Command: `npx playwright test --project=...`
- Result: N passed / M failed / K skipped
- Verdict: PASS | FAIL | PARTIAL (name what wasn't verified)

| Scenario | Target AC (FR/NFR) | Result | Evidence (trace/screenshot path, measured time) |
|---|---|---|---|

- Failures: (added as KI-xxx)
- UX issues: (with measurements)
- Regression: existing scenarios re-run and their results
- Not verified, and why:
```

## Test records

### QA-001 · 2026-11-14 · T-026 Locust smoke + load against the mock LLM (FR-009)
- Environment: `system-docker-compose.yaml` infra (fresh volumes); host uvicorn (single process) + ingest worker with `OPENAI_BASE_URL=http://localhost:9000/v1 OPENAI_API_KEY=sk-mock LANGFUSE_*` empty; mock OpenAI :9000; real fastembed e5 locally; Apple M2 8-core 16 GB, everything on one machine. Frontend not involved. Prometheus not started.
- Command: `LOADTEST_SCENARIO=smoke|load uv run locust -f locustfile.py --headless --host http://localhost:8000 --csv reports/<name>` (full details in `loadtest/RESULTS.md`)
- Result: smoke 92 req / 0 fail, exit 0; load 22,367 req / 9 fail (0.04%), exit 1
- Verdict: PARTIAL. smoke PASS; load FAIL on the chat p95 gate (3900 ms > 3000 ms). stress/soak/spike/breakpoint not run.

| Scenario | Target AC (FR/NFR) | Result | Evidence |
|---|---|---|---|
| smoke | FR-009 | PASS, chat p95 2300 ms, same as the previous smoke | `loadtest/reports/smoke_stats.csv` |
| load T=50 | FR-009 | FAIL gate, steady p95 about 2.2 s, whole-run 3900 ms from stalls | `loadtest/reports/load_stats*.csv`, `load.log` |

- Failures: KI-023, KI-024
- Not verified, and why: stress/soak/spike/breakpoint (out of scope); Prometheus targets (skipped to avoid load); cause of the stalls (not profiled).


### QA-002 · 2026-11-26 · T-041 E2E of T-033/T-038/T-039/T-040 (chat memory, history restore, turn lock, uploads, drawer)
- Environment: Docker infra (postgres/redis/qdrant/kafka); host uvicorn :8000, ingest worker, vite :5173; Playwright MCP chromium 1280x800 and 390x844; real OpenAI gpt-4o-mini, 11 billed turns. Seeded users 254 (A) and 255 (B) plus `google_sessions` rows, cookie `session=`. API had to run with `REDIS_PORT=6380 REDIS_PASSWORD=` against a throwaway passwordless `redis:latest` container because of KI-057. No spec file written (exploratory run via Playwright MCP); no `npx playwright test`.
- Result: 10 behaviours checked, 9 PASS / 1 PARTIAL, plus 1 CRITICAL found (KI-057). Verdict: FAIL on stock infra (every chat turn 500), PASS once Redis auth is bypassed.

| Behaviour | Result | Evidence |
|---|---|---|
| Baseline with stock Redis | FAIL | 3 of 3 sends 500 in 4.0-5.0 s, UI error box with Retry, 0 rows stored; `.playwright-mcp/qa002-redis-auth-500.png`; KI-057 |
| 1 multi-turn memory | PASS | fact -> unrelated turn -> recall answered "Your favorite number is 7342."; `qa002-memory.png` |
| 2 reload restores history and chip | PASS | 6 messages restored, chip "Agent chooses · gpt-4o-mini"; pinned chat chip "qa002_tmp · gpt-4o-mini", assistant row has 4 citations via history API; `qa002-reload.png`, `qa002-pinned-answer.png` |
| 3 second send while pending -> 409 | PASS | curl 409 in 20 ms; UI send gave 409 in 106 ms, alert "Still answering your previous message. Wait a moment, then retry." + Retry; Retry after the lock freed -> 200 (2.2 s); `qa002-409.png` |
| 4 failed turn stores nothing, chat still works | PARTIAL | forced by stopping Redis (pre-LLM failure): 500 in 3.9 s, `chat_messages` stayed 12 -> 12, Retry after restart -> 200, checkpoints 1. A mid-turn LLM/Qdrant failure was NOT forced (deleting a pinned collection made the agent answer from memory instead of failing); `qa002-failed-turn.png` |
| 5 other user's chat | PASS | A GET/POST on B's chat -> 403, unknown id -> 404, no cookie -> 401; B's chat stays at 0 messages; UI shows "This conversation isn't available..." (`qa002-forbidden-ui.png`) |
| 6 New chat while pending | PASS | old answer did not appear in the new chat (clean empty state); server finished (7.6 s, 200) and the answer is in the old chat's history; `qa002-newchat-pending.png` |
| 7 .md upload | PASS | 2 files x2 (my double `setFiles`) all "Indexed (1/1 chunks)" within seconds, per-file lines shown, 0 `/status` requests in 6 s after INDEXED, Points 4; `qa002-upload-progress.png` |
| 8 mobile 390px drawer | PASS | no horizontal scroll; aside closed (null box) -> opens 256x844, toggle label becomes "Close navigation" with aria-expanded, link click and Escape both close it, focus returns to "Open navigation"; `qa002-mobile-drawer-open.png` |
| 9 Korean IME Enter | PASS (best effort) | synthetic keydown Enter with `isComposing:true` -> 0 POSTs, text kept; CDP `imeSetComposition` + Enter -> 0 POSTs. Real IME not driven |
| 10 timings | note | chat turn 1.5-2.6 s (short), 3.8 s with retrieval, 8.8-9.7 s for 400-word essays, no progress bar but the thinking indicator shows; collection create 261 ms; failed-turn 3.9-5.0 s |

- Checkpoint pruning: `checkpoints` = 1 row per thread after 7-14 stored messages (3 test threads, 3 rows total); `checkpoint_blobs` 1-2 per thread, `checkpoint_writes` 0.
- My usage: 11 chat messages for gpt-4o-mini matched the 11 billed turns exactly; embedding docs 4.
- Console: only expected 409/500/403 resource errors from the induced failures.
- Failures: KI-057 (critical), KI-058, KI-059 (minor)
- Cleanup: deleted users 254/255, 2 sessions, 5 chats, 22 chat_messages, 11 chat_usage_logs, 2 agent_tool_call_logs, 4 document_manage_logs, 4 document_progress_status, 3 checkpoints, 5 checkpoint_blobs; verified 0 left; Qdrant `qa002_tmp` deleted (only rag_eval_papers/rag_eval_v2 remain); throwaway Redis, API, worker and vite stopped. Also note: the Playwright MCP browser had stale context-level `page.route` mocks (fake /auth/me, /models) that I cleared with `unrouteAll`.
- Not verified, and why: real mid-turn LLM failure, Redis lock expiry/TTL with a crashed worker, desktop keyboard-only/axe pass, multi-tab history refresh (known KI-053), Playwright spec in `eval/tests/e2e/` (not asked).

### QA-003 · 2026-11-27 · T-041 re-check of KI-057/058/059 fixes
- Environment: stock passworded Redis :6379 (no throwaway), host uvicorn default env + vite; worker not started; Playwright MCP chromium 1280x800 with stale route mocks cleared; seeded users 256/257; 4 billed chat turns (2 memory + 1 slow essay holding the lock; the 409 sends were rejected unbilled).
- Result: 5/5 PASS. Verdict: PASS.

| Check | Result | Evidence |
|---|---|---|
| 1 2-turn memory with stock Redis | PASS | 200 in 1.7 s and 1.0 s; "Your lucky color is teal." (KI-057 fixed) |
| 2 concurrent send -> 409 UI | PASS | 409, alert "Still answering your previous message. Wait a moment, then retry." + Retry; `qa003-409-draft.png` |
| 3 403 body without ids | PASS | `{"detail":"You do not have access to this chat."}` for GET and POST; unknown id `{"detail":"Chat not found."}` 404 (KI-058 fixed) |
| 4 other user's chat hides input | PASS | 0 textbox and 0 Send buttons, "This conversation isn't available..." ; `qa003-forbidden.png` |
| 5 draft restored after failed send | PASS | textarea kept "draft to keep after 409" after the 409 |

- Cleanup: removed 2 users, 2 sessions, 2 chats and their messages, usage/tool logs and checkpoints (before-counts printed in the run; after = 0 rows); API and vite stopped; no Redis/Qdrant changes.
- Not re-verified: KI-059 empty-chat row after a failed first turn and orphan `document_progress_status` rows on collection delete.
