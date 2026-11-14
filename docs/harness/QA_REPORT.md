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

