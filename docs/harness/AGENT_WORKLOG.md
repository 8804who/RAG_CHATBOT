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


