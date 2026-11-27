# Decision Log

> Owners: `system-architect` (technical/design), `rag-llm-scientist` (LLM/RAG selection), `pm` (records user decisions). Append-only; to reverse a decision, write `Supersedes: D-xxx` in a new entry.
> Other agents who need a decision send the evidence to the owner ([HANDOFF_PROTOCOL.md §8](HANDOFF_PROTOCOL.md#8-conflict-resolution)).

## Format

```markdown
### D-xxx · Title
- Date: YYYY-MM-DD
- Decided by: <agent or user>
- Status: Accepted | Superseded by D-yyy
- Context: what the problem was
- Decision: what was decided
- Alternatives: other options considered and why they were dropped
- Impact: docs and code that change
```

## Earlier decisions (pre-harness, migrated 2026-11-14 from `CLAUDE.md` and design docs)

D-001 to D-008 record decisions already reflected in the code. Their original dates weren't recorded.

### D-001 · Ingestion is async via Kafka; chat is synchronous request-response
- Date: pre-harness (migrated 2026-11-14)
- Decided by: project (existing)
- Status: Accepted
- Context: embedding and chunking are slow and can fail; chat needs an immediate answer.
- Decision: upload produces to Kafka and returns 202; parser/embed/index stages process it. The read path doesn't use Kafka.
- Alternatives: synchronous ingestion (request timeouts, hard retries) — details in [`docs/RAG_ARCHITECTURE.md`](../RAG_ARCHITECTURE.md) §2.
- Impact: all three stages must be running to reach `INDEXED`. (Today the stages run as three consumer groups inside the single `workers.ingest_worker` process.)

### D-002 · A tool-calling agent (LangChain/LangGraph) instead of a fixed pipeline
- Date: pre-harness (migrated 2026-11-14)
- Decided by: project (existing)
- Status: Accepted
- Context: queries need different behavior: multi-collection search, multi-step search, calculation, web search.
- Decision: a `create_agent`-based agent chooses tools. The old `services/chat/`, `services/generation/`, `clients/llm/` were removed.
- Alternatives: a single retrieve→generate call (simple and cheap, but no multi-step queries).
- Impact: the number of LLM calls per turn varies → tokens are summed per turn.

### D-003 · Calculator uses `simpleeval`; no code-execution tool
- Date: pre-harness (migrated 2026-11-14)
- Decided by: project (existing)
- Status: Accepted
- Context: a Python REPL reachable from a chat prompt is unsandboxed remote code execution.
- Decision: `simpleeval`, which evaluates arithmetic only.
- Alternatives: a Python REPL tool — rejected as a security risk.
- Impact: `services/agent/tools.py::build_calculator_tool`.

### D-004 · The usage tool calls a requester-scoped service; no free-form SQL
- Date: pre-harness (migrated 2026-11-14)
- Decided by: project (existing)
- Status: Accepted
- Context: the same Postgres holds `users`, `google_sessions`, and other users' chats.
- Decision: wrap `UsageStatsService.get_user_stats` with `requester_id` fixed.
- Alternatives: an LLM-written SQL tool — rejected for data exposure and injection risk.
- Impact: `build_usage_stats_tool`.

### D-005 · Citations re-parse ToolMessage JSON
- Date: pre-harness (migrated 2026-11-14)
- Decided by: project (existing)
- Status: Accepted
- Context: answer sources must reach the client in structured form.
- Decision: after the run, find `search_documents` / web `ToolMessage` content (JSON) by name, parse it, and dedupe by `chunk_id`/`url`.
- Alternatives: LangChain `response_format="content_and_artifact"` — rejected for compatibility issues with the prebuilt agent graph.
- Impact: `_extract_citations`, `Citation.source_type`.

### D-006 · One embedding model fixed per collection
- Date: pre-harness (migrated 2026-11-14)
- Decided by: project (existing)
- Status: Accepted
- Context: vectors from different models can't be compared in the same space.
- Decision: fix the model and dimension in `CollectionMeta` at creation; both ingestion and search use that model.
- Alternatives: none (a consistency requirement).
- Impact: [`docs/EMBEDDING_AND_COLLECTIONS.md`](../EMBEDDING_AND_COLLECTIONS.md).

### D-007 · Hybrid search uses Qdrant server-side RRF
- Date: pre-harness (migrated 2026-11-14)
- Decided by: project (existing)
- Status: Accepted
- Context: combine keyword match (BM25) and semantic search (dense).
- Decision: collections with sparse config do dense + sparse prefetch, then `FusionQuery(RRF)`. Whether a collection has sparse vectors is checked in Qdrant at query time.
- Alternatives: weighted-sum fusion (needs weight tuning) — not adopted, open for re-evaluation.
- Impact: `RetrievalService`, `QdrantRepository.search`.

### D-008 · Separate cookie names for OAuth state and auth
- Date: pre-harness (migrated 2026-11-14)
- Decided by: project (existing)
- Status: Accepted
- Context: if both are `session`, `SessionMiddleware` deletes the auth cookie in the callback response and `/auth/me` returns 401.
- Decision: `SessionMiddleware(session_cookie="oauth_state")`; auth uses `session`.
- Alternatives: none.
- Impact: `main.py`.

## Decisions since the harness

### D-009 · Adopt the multi-agent harness, with `docs/harness/` as the shared SSOT
- Date: 2026-11-14
- Decided by: user
- Status: Accepted
- Context: agents can't share conversation context, so decisions and status got scattered.
- Decision: `docs/harness/` and [HANDOFF_PROTOCOL.md](HANDOFF_PROTOCOL.md) are the common rules for all agents. Existing docs (`CLAUDE.md`, `.claude/.rules/`, `docs/*.md`) stay canonical and are only linked. The PM agent's management docs moved from `docs/pm/` to `docs/harness/`.
- Alternatives: keep `docs/pm/` separately — rejected as duplication.
- Impact: `CLAUDE.md` Harness section, the 10 `.claude/agents/*.md` files.

### D-010 · Load tests use a mock LLM + a standalone `loadtest/` project; the scenario doc lives in `loadtest/`
- Date: 2026-11-14
- Decided by: `system-architect` (T-003)
- Status: Accepted (rationale for (e) replaced by D-011; design kept)
- Context: FR-009/NFR-007. Measure the limits of our infra (FastAPI, DB pool, Qdrant, agent graph) without changing app code, and without real OpenAI billing, latency, or rate limits polluting the results.
- Decision:
  (a) During load runs the backend points at `loadtest/mock_openai.py` via shell env `OPENAI_BASE_URL=http://localhost:9000/v1 OPENAI_API_KEY=sk-mock` (a dummy key, so a missing base URL fails with 401 and costs nothing). Langfuse is disabled with `LANGFUSE_PUBLIC_KEY= LANGFUSE_SECRET_KEY=`. The locustfile exits immediately if an answer doesn't start with `[mock]` (second billing guard).
  (b) The scenario design doc is `loadtest/SCENARIOS.md`, because `.gitignore` ignored all of `docs/` at the time; it sits where it's committed with the code. (Since D-014, `docs/` is versioned; the location stays.)
  (c) `loadtest/` Python uses the backend's Korean comment/docstring format, but not the `.claude/.rules/` layering (endpoint→service→repository→client, `get_*` singleton DI) — it's a single-script tool.
  (d) Only single-process Locust is supported: the OAuth-bypass user/session seed lives in process memory and the breakpoint stop rule reads local stats. By calculation one core handles ~500 users / 116 RPS, which is enough.
  (e) The load shape is one `LoadTestShape` that reads env `LOADTEST_SCENARIO`. Ramps are built as a per-tick interpolated target + fixed spawn rate (because Locust `start()` blocks ticks during a ramp); the shape applies `-t` itself (Locust ignores it in headless shape mode).
- Alternatives: load with real OpenAI — rejected: cost, rate limits, and latency variance hide the infra limits. Doc in `docs/` — rejected: not committed. Distributed Locust — rejected: needs a shared seed pool, unnecessary at this scale. Several shape classes per scenario — rejected: Locust uses only the first.
- Impact: `loadtest/SCENARIOS.md` (new), `loadtest/locustfile.py` and `loadtest/README.md` (T-004), one link line in `SYSTEM_ARCHITECTURE.md`.

### D-011 · Correct the rationale of D-010(e)'s ramp implementation
- Date: 2026-11-14
- Decided by: `system-architect` (T-006)
- Status: Accepted
- Supersedes: the rationale of D-010 (e) (the design stays)
- Context: D-010(e) cited "Locust `start()` blocks ticks during a ramp" (a TODO in `runners.py` `shape_worker`). T-004 found that the `LocalRunner.start` we use (locust 2.47 `runners.py:550-564`) kills the running spawn greenlet, starts a new one, and returns immediately. Only `MasterRunner.start` (distributed) blocks: it runs the dispatcher in place, and the dispatcher `gevent.sleep`s to match the spawn rate (`dispatch.py:298`).
- Decision: ramps stay "per-tick interpolated target + fixed spawn rate 100". The rationale becomes: (1) the user count is set exactly every second as `ceil(prev + (u − prev) × progress)`; (2) it doesn't depend on Locust spawn-rate behavior that differs per runner (local kills the previous spawn and returns, master blocks); (3) the breakpoint stop rule and the `-t` cap are evaluated in `tick()` every second.
- Note: D-010(c)'s "single-script tool" became a package after T-004 (`core/`, `shapes/`, `users/`, `tasks/`, `utils/`, entry point `locustfile.py`). The decision not to apply the layering stands.
- Alternatives: edit the D-010 body — rejected by the append-only rule.
- Impact: only the common-rules wording in `loadtest/SCENARIOS.md` §4. No code change.

### D-012 · Local monitoring is a separate compose project (Prometheus + exporters + Grafana); backend app metrics later
- Date: 2026-11-14
- Decided by: `system-architect` (T-008)
- Status: Accepted (PM approval 2026-11-14, T-008)
- Context: no way to see infra health (Postgres/Redis/Qdrant/Kafka/ingest-worker) or Kafka consumer lag. The existing `docker-compose.yaml` was not to be touched.
- Decision:
  (a) Repo-root `monitoring-docker-compose.yaml` + `monitoring/**`. Top-level `name: rag_chatbot_monitoring` is required — in the same directory without a name it would be the same project as the main stack, and `--remove-orphans`/`down` would touch the main services.
  (b) The network is the main project's default network, referenced as `networks.default: {name: <main>_default, external: true}`; the main stack must start first. (At the time `rag_chatbot_default`; since T-020 the infra project is `rag_chatbot_system`, so it's `rag_chatbot_system_default`.)
  (c) Secrets only via `env_file: docker.env`. The Prometheus config can't read env, so at container start `sh -c` writes `QDRANT__SERVICE__API_KEY` to `/tmp/qdrant_api_key` and `exec /bin/prometheus`; the qdrant job uses `authorization: {type: Bearer, credentials_file: /tmp/qdrant_api_key}` (Qdrant treats `Authorization: Bearer` like the `api-key` header). postgres-exporter assembles `DATA_SOURCE_USER/PASS/URI` the same `sh -c` way (no password in the URI, avoiding special-character issues). redis-exporter reads the `REDIS_PASSWORD` env directly.
  (d) Host metrics come from one cAdvisor (per-container CPU/memory — fastembed worker and Qdrant memory matter). node-exporter is excluded: on macOS Docker Desktop it shows the LinuxKit VM, not the Mac, and overlaps cAdvisor's root cgroup.
  (e) FastAPI `/metrics` and worker metrics are a follow-up: they need code and dependency changes, and request latency/tokens are already recorded by `ApiCallLogMiddleware` and Langfuse. Until then there is no `api` scrape job. (Done later at the user's request in T-015.)
- Alternatives: add services to the main compose — rejected (existing file off-limits). Render the Prometheus config from a template (envsubst) — overkill for one key. `http_headers.api-key.files` — works, but `authorization` is simpler and standard. node-exporter — rejected per (d).
- Impact: new `monitoring-docker-compose.yaml`, `monitoring/prometheus/prometheus.yml`, `monitoring/grafana/provisioning/datasources/prometheus.yml`. No app code change.

### D-013 · Existing Docker volume data need not be preserved (user decision)
- Date: 2026-11-14
- Decided by: user (via the main session), recorded by PM
- Status: Accepted
- Decision: local volumes hold only test data, so the compose split (T-020) adds nothing to preserve volume names. Recreating or deleting volumes is allowed. Agents still don't run destructive docker commands themselves; cleanup commands are given to the user as steps.
- Impact: the infra project is named `rag_chatbot_system` (user request, T-020 revision) so the service and monitoring stacks can join the predictable network `rag_chatbot_system_default`. Volumes are now `rag_chatbot_system_*`.

### D-014 · Version the harness and agent definitions in git (user decision)
- Date: 2026-11-14
- Decided by: user (via the main session), recorded by PM (T-025)
- Status: Accepted
- Context: `.gitignore` ignored `CLAUDE.md`, `.claude/`, and `docs/`, so the harness, agent definitions, rules, and design docs existed only locally.
- Decision: track `CLAUDE.md`, `.claude/agents/`, `.claude/.rules/`, and `docs/`. Keep `.claude/settings*.json`, `.claude/mcp/`, `.claude/skills/`, and `docs/career/` (private notes) ignored. Agent-facing docs (`docs/harness/`, `.claude/`) are written in English; code comments/docstrings stay Korean per `.claude/.rules/`.
- Alternatives: keep everything local — rejected, harness changes had no history or review.
- Impact: `.gitignore`; a secret scan of the newly tracked files found only the dummy `sk-mock` (D-010(a)).

### D-015 · Adopt the Spotify-inspired design system (user decision)
- Date: 2026-11-26
- Decided by: user (via the main session), recorded by the main session acting as pm (T-032)
- Status: Accepted
- Context: `.claude/.rules/design.md` asked for a light Instagram/LinkedIn-style SaaS look; the user asked to use `.claude/design/DESIGN-spotify.md` instead.
- Decision: `DESIGN-spotify.md` is the canonical visual system (dark `#121212` base, `#1ed760` accent only for primary CTA/active, pill buttons, uppercase button labels, heavy shadows on dark). UX/form/a11y/responsive rules in `design.md` still bind. No Spotify name, logo, or proprietary fonts.
- Alternatives: rule-only adoption (no restyle) or restyle without changing rules — rejected by the user.
- Impact: `.claude/.rules/design.md`, `docs/harness/DESIGN_GUIDELINES.md`, all of `frontend/src`.

### D-016 · Chat state ownership: checkpoints are agent memory, `chat_messages` is the display transcript; a turn is all-or-nothing
- Date: 2026-11-26
- Decided by: `system-architect` (T-036)
- Status: Accepted by PM 2026-11-26 with amendment to (c): the per-chat lock uses Redis `SET NX EX` (released in `finally`), not `FOR UPDATE NOWAIT`/advisory lock, because both pin a DB connection for the whole LLM call and conflict with releasing connections during the turn (KI-010 fix). History endpoint scope: `GET /chats/{chat_id}/messages` only (no chat list yet).
- Context: T-033 added a LangGraph `AsyncPostgresSaver` beside `chat_messages`. Both are written per turn with no compensation, no per-chat lock, and no pruning (SYSTEM_ARCHITECTURE.md, "Structural risks").
- Decision:
  (a) `chat_messages` stays the user-visible transcript (future history/list endpoints read it); checkpoints are only the model's working memory and are never shown to users.
  (b) A turn commits both or neither: on agent failure, remove the turn's messages from the thread (`aupdate_state` with `RemoveMessage` for everything since the turn's `HumanMessage`) and delete or mark the user `chat_messages` row; the client gets the error and can resend.
  (c) One turn per chat at a time: `SELECT ... FOR UPDATE NOWAIT` on the `chats` row (or a Postgres advisory lock) at turn start → 409 on a second concurrent send. Redis is not needed for this.
  (d) After a successful turn, `checkpointer.aprune([chat_id], strategy="keep_latest")`, and run with `durability="exit"`; deleting a chat later calls `adelete_thread`.
- Alternatives: drop `chat_messages` and render from checkpoints — rejected (checkpoint state is summarized and holds raw tool JSON; schema is LangGraph-owned). Rebuild memory from `chat_messages` each turn (no checkpointer) — viable and simpler, but loses tool results across turns; revisit if checkpoint ops cost too much.
- Impact: `services/agent/agent_orchestrator.py`, `repositories/chat_repository.py`; no schema change.
