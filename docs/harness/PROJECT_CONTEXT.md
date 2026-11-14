# Project Context

> Owner: `pm` · Canonical sources: code structure [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md), commands [`/CLAUDE.md`](../../CLAUDE.md), layering rules `.claude/.rules/`. This doc holds only a summary and the current stage.

## Purpose

An **agentic RAG chatbot** that answers from documents users upload (an internal knowledge base). Answers carry source citations (document chunks or web sources).
As a portfolio project, it values a structure that supports "measure → improve → compare before/after" (eval harness; token, cost, and latency logging).

## Main features (implemented)

| Feature | Screen | Backend |
|---|---|---|
| Google OAuth login, session cookie | `/login` | `/api/v1/auth/*` |
| Collection management (embedding model and dimension fixed, dense + sparse vectors) | `/collections` | `/api/v1/collections` |
| Document upload → async Kafka ingestion → status tracking | `/documents` | `/api/v1/collections/{name}/documents` + `workers.ingest_worker` (parser/embed/index consumer groups in one process) |
| Agentic RAG chat (multi-collection search, calculator, usage, arXiv, web search tools) + citations | `/chat` | `/api/v1/chats` |
| Model catalog (embedding, chat) | choices on each screen | `/api/v1/models` |
| Usage and cost stats | `/my` | `/api/v1/usage/stats` |

## Tech stack

- **Backend:** Python 3.13, FastAPI, SQLAlchemy async (asyncpg), Alembic, `uv`, LangChain/LangGraph, Langfuse, Prometheus metrics (`/metrics`)
- **Frontend:** Vite, React 19, TypeScript, Tailwind v4, React Query v5, React Router v7
- **Infra (docker compose):** `system-docker-compose.yaml` — PostgreSQL, Redis (+RedisInsight), Qdrant, Kafka (+Kafka UI); `service-docker-compose.yaml` — api, frontend (nginx), ingest-worker (non-root); `monitoring-docker-compose.yaml` — Prometheus, Grafana, exporters, cAdvisor, Loki, Alloy
- **LLM/embedding:** OpenAI (`gpt-4o-mini`, `gpt-4o`, `text-embedding-3-*`), fastembed (`multilingual-e5-large`), BM25 sparse — details in [LLM_SPECIFICATION.md](LLM_SPECIFICATION.md)
- **Eval:** Playwright + TypeScript (`eval/`), LLM-as-judge

## Directories

```
backend/app/     FastAPI app (import root). api → services → repositories → clients
backend/tests/   pytest, mirrors app/
frontend/src/    pages, components, hooks (React Query), lib/api (API layer), auth
eval/            Playwright RAG eval harness (+ qa-engineer E2E: eval/tests/e2e/)
loadtest/        Locust load tests against an OpenAI mock
monitoring/      Prometheus, Grafana provisioning, Loki, Alloy config
docs/            design docs, docs/harness/ (this system); docs/career/ is private and gitignored
.claude/agents/  10 agent definitions · .claude/.rules/ coding rules
```

## Core domain terms

| Term | Meaning |
|---|---|
| Collection | A Qdrant collection + Postgres `CollectionMeta`. All vectors in a collection share one embedding model and dimension. |
| Document | A virtual concept: the set of chunks sharing a `document_id` payload (no documents table; only progress in `document_progress_status`). |
| Chunk | A text unit cut by a word window (400) + overlap (80), stored as dense (+sparse) vectors. |
| Ingest status | `UPLOADED → PARSING → EMBEDDING → INDEXED`, or `FAILED`. |
| Chat / pinned collection | If a collection is pinned at chat creation, only it is searched; otherwise the agent picks collections per query. |
| Turn | One agent run for one user message (may make several LLM calls). Tokens are summed and recorded per turn. |
| Citation | Answer evidence. `source_type` is `document` (chunk) or `web` (URL). |

## Current stage (as of 2026-11-14)

- All core features are wired to the real backend (no frontend mocks). Chat is non-streaming.
- Recent work: switched to a LangChain/LangGraph agent, added the arXiv search tool, store agent tool-call logs (`agent_tool_call_logs`); load tests (`loadtest/`); local monitoring and logging stack; backend and frontend run as non-root containers.
- Direction: a measure-first roadmap — measure quality, cost, and latency with eval, then improve.
- 2026-11-14: multi-agent harness (this directory) adopted; versioned in git since D-014.
