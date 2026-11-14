# Load test (Locust)

Load tests for the chat API, with the LLM replaced by a mock, so they measure only our own infra. Scenario design, SLOs, and capacity hypotheses are in [SCENARIOS.md](SCENARIOS.md). This file covers only how to run it.

## Prerequisites

1. Infra: `docker compose up -d` (repo root)
2. DB schema: `uv run alembic upgrade head` (`backend/app`)
3. The `rag_eval_papers` collection is ingested (see [eval/README.md](../eval/README.md)). Pinned chats fail with `empty citations (pinned)` if it is empty.
4. Dependencies: `uv sync` (`loadtest/`)

## Run

Start each process in its own terminal.

```bash
# 1) mock OpenAI (loadtest/, :9000)
uv run python mock_openai.py

# 2) backend pointed at the mock, Langfuse disabled (backend/app). Never start it without these env vars: that bills the real OpenAI
OPENAI_BASE_URL=http://localhost:9000/v1 OPENAI_API_KEY=sk-mock LANGFUSE_PUBLIC_KEY= LANGFUSE_SECRET_KEY= \
  uv run uvicorn main:app --port 8000

# 3) Locust (loadtest/). Seeding needs POSTGRES_USER/PASSWORD/DB (same values as repo-root docker.env)
set -a; . <(grep '^POSTGRES_' ../docker.env); set +a
LOADTEST_SCENARIO=smoke uv run locust -f locustfile.py --headless --host http://localhost:8000 --csv reports/smoke
```

- Scenarios: `smoke | load | stress | spike | soak | breakpoint`. Order and env knobs (`LOADTEST_TARGET_USERS`, `LOADTEST_COLLECTION`, `LOADTEST_CHAT_P95_MS`) are in [SCENARIOS.md §3–4](SCENARIOS.md).
- `-t 90s` stops early (the shape enforces it itself). `-t` and the breakpoint grace period count from when seeding finishes, not from process start. Ctrl+C also exits cleanly (stats written, seeded sessions deleted).
- Web UI: drop `--headless` and open http://localhost:8089. The scenario is still chosen with `LOADTEST_SCENARIO`.
- Exit code: smoke/load/stress/soak return 1 if they fail the pass gate in SCENARIOS.md §5. A non-mock (real OpenAI) answer stops the run immediately and returns 1. So do a failed seed, zero chat turns, an unhandled Locust exception, and a failed session cleanup.
- spike/breakpoint have no pass gate, so their exit code is not a pass/fail verdict: Locust's default returns 1 if even one request failed.
- Self-check (no DB/server needed): `uv run python selfcheck.py` checks stage-table ticks, `-t`, breakpoint stop rules, the seeding gate, and response validation.
- Single-process only (`--processes`/`--worker` are not supported).

## Reports

`--csv reports/<name>` writes `reports/<name>_stats.csv`, `_stats_history.csv`, `_failures.csv` and `_exceptions.csv`. Add `--csv-full-history` for spike's manual verdict. `reports/` is in `.gitignore`.

## Layout

| Path | Role |
|---|---|
| `locustfile.py` | Entry point (exposes the User/Shape classes, registers hooks) |
| `core/config.py` | Env validation, constants, query corpus, scenario stage tables |
| `core/hooks.py` | `test_start` seeding, `test_stop` session cleanup, `quitting` pass gate |
| `users/` | `ChatUser` (weight 4), `BrowseUser` (weight 1) |
| `tasks/` | Per-user task functions |
| `shapes/scenario.py` | Stage-table load shape, `-t` enforcement, breakpoint auto-stop |
| `utils/` | Seeded session pool (DB), HTTP helper, chat response validation |
| `mock_openai.py` | OpenAI-compatible mock (`/v1/chat/completions`, `/v1/embeddings`) |
