# CLAUDE.md

RAG chatbot monorepo. It has an agentic RAG chat: a LangChain/LangGraph tool-calling agent over Qdrant, non-streaming. It also has Google OAuth login, Kafka-based document ingestion, and a React SPA.

| Path | What | Details |
|---|---|---|
| `backend/` | FastAPI, `uv`, Python 3.13; code in `backend/app` | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| `frontend/` | Vite + React 19 + TypeScript SPA | [`docs/ARCHITECTURE.md#frontend`](docs/ARCHITECTURE.md#frontend) |
| `eval/` | Playwright harness against the live chat API (quality, tokens, latency) | `eval/README.md` |
| `loadtest/` | Locust against an OpenAI mock (no LLM spend) | `loadtest/README.md`, `loadtest/SCENARIOS.md` |
| `system-docker-compose.yaml` | Infra: Postgres :5432, Redis :6379 (+Insight :5540), Qdrant :6333/:6334, Kafka :9092 (+UI :8080) | |
| `service-docker-compose.yaml` | App containers (non-root): api :8000, frontend :5173, ingest-worker | [`docs/ARCHITECTURE.md#run-in-docker`](docs/ARCHITECTURE.md#run-in-docker) |

**Read only the part you need:**
- Code-level architecture, request flows, gotchas, config/env: `docs/ARCHITECTURE.md`
- Coding rules (binding): `.claude/.rules/` — `code.md`, `annotation.md`, `test_code.md`, `log.md`, `design.md`
- Design rationale: `docs/RAG_ARCHITECTURE.md`, `docs/KAFKA_INGESTION.md`, `docs/EMBEDDING_AND_COLLECTIONS.md`
- Multi-agent harness: `docs/harness/README.md`, `docs/harness/HANDOFF_PROTOCOL.md`

## Multi-agent harness (must follow)

- Development requests (code, design, research, review, testing) go through `.claude/agents/`. Multi-part or cross-specialty work goes to `pm` (or run the session as `claude --agent pm`). Small single-specialty work can go straight to that specialist, plus the matching code reviewer for code changes; whoever delegated updates `TASK_BOARD.md` / `AGENT_WORKLOG.md` (ownership: `docs/harness/HANDOFF_PROTOCOL.md` §2). Pure questions need no agents and no doc updates.
- **Context budget:** a subagent's only context is its brief: a compact one in the `HANDOFF_PROTOCOL.md` §6 format, at most 30 lines. Subagents read only what the brief names, update only their own specialty docs, and report back in ≤ 15 lines. Subagents never update `TASK_BOARD.md` or `AGENT_WORKLOG.md`. Never record a test, review, or verification that wasn't actually run.
- **Language:** Agent-facing docs (docs/harness/, .claude/) are written in English; code comments/docstrings stay Korean per .claude/.rules/.
- **Priority on conflict:** user's explicit request > `CLAUDE.md`, `.claude/.rules/`, `REQUIREMENTS.md` > `SYSTEM_ARCHITECTURE.md` > `DECISION_LOG.md` > other harness docs > the current task instruction. Don't resolve conflicts silently.
- When code and docs disagree, the code is the fact; the doc owner fixes the doc.

## Rules that bite (full text in `.claude/.rules/`)

- **Backend:** Korean comments and docstrings. Layering is endpoint → service → repository → client. Services and repositories are `@lru_cache`'d `get_*` singletons in `dependencies/`. Logs go in the service/worker layer only. Every entrypoint calls `configure_logging()`. `AppException.message` is shown to the client.
- **Frontend:** no `any`, no `export default`. API calls go only through `src/lib/api/`. Tailwind only.

## Commands

```bash
docker compose -f system-docker-compose.yaml up -d             # 1. infra (repo root)
docker compose -f service-docker-compose.yaml up -d --build    # 2. api + frontend + ingest-worker in Docker (or run locally below)
docker compose -f monitoring-docker-compose.yaml up -d         # 3. optional monitoring

# backend — always from backend/app (the import root)
uv sync && uv run alembic upgrade head
uv run uvicorn main:app --reload --port 8000  # API (only produces to Kafka)
uv run python -m workers.ingest_worker        # needed for document ingest
uv run ruff check . && uv run ruff format .
uv run pytest [tests/path::test_name]         # tests in backend/tests/, mirroring app/

# frontend — from frontend/
npm install && npm run dev                    # :5173, proxies /api → :8000
npm run build && npm run lint
```

eval and loadtest: see their READMEs. Secrets are in `backend/app/.env` and `docker.env`, both gitignored.

<!-- code-review-graph MCP tools -->
## code-review-graph MCP

Narrow scope with the graph first: `query_graph_tool` (callers_of / tests_for / importers_of), `get_impact_radius_tool`, and `detect_changes_tool` + `get_review_context_tool` for reviews. Then verify in the source. The source wins, and an empty result can mean "not indexed".
<!-- /code-review-graph MCP tools -->
