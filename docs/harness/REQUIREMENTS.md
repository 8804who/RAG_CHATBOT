# Requirements

> Owner: `pm` · Add or change requirements only after the user confirms. Never finalize a scope change without user approval.

## Writing rules

- IDs: functional `FR-xxx`, non-functional `NFR-xxx`. Last number + 1, checked right before adding.
- Status: `PROPOSED` (not approved by the user) · `APPROVED` · `IMPLEMENTED` (code exists, AC not verified) · `VERIFIED` (AC verified by tests/QA) · `DROPPED`.
- Write acceptance criteria as testable statements ("fast" ✗ → "p95 < 3s" ✓).
- On any change, add one line to the change history at the bottom.

## Baseline (features already implemented when the harness was adopted)

These were reverse-documented from the code on 2026-11-14, when the harness was adopted. There were no formal AC, so the status is `IMPLEMENTED` and the AC describe current code behavior. Promote to `VERIFIED` once tied to tests/QA.

### Functional requirements

| ID | Requirement | AC (current behavior) | Status |
|---|---|---|---|
| FR-001 | Log in/out with a Google account | After login a `session` cookie is issued and `GET /auth/me` returns 200 / after logout 401 / protected routes redirect unauthenticated users to `/login` | IMPLEMENTED |
| FR-002 | Create, read, update, delete collections | 400 when the embedding model + dimension don't match the catalog / 409 for a duplicate name / 404 for a missing collection | IMPLEMENTED |
| FR-003 | Document upload and async ingestion | 202 + `document_id` right after upload / with the ingest worker running (parser/embed/index stages), status reaches `INDEXED` or `FAILED` (with reason) | IMPLEMENTED |
| FR-004 | List documents, view chunks, delete | Per-collection document list, per-document chunks, delete 204 / every ingest and delete logs success or failure | IMPLEMENTED |
| FR-005 | Agentic RAG chat | Pinned collection or agent choice / returns answer and citations / 403 on someone else's chat | IMPLEMENTED |
| FR-006 | Agent tools | Document search (multi-collection), calculator, my usage, arXiv search, web search (only with `TAVILY_API_KEY`) | IMPLEMENTED |
| FR-007 | Model catalog | `GET /models` returns embedding and chat model lists | IMPLEMENTED |
| FR-008 | Usage and cost stats | Per-user embedding and chat tokens and cost (`cost=null` for models without pricing) | IMPLEMENTED |

### Non-functional requirements

| ID | Requirement | AC (current behavior) | Status |
|---|---|---|---|
| NFR-001 | Security: session-based auth | Protected APIs return 401 without a valid session / OAuth state cookie (`oauth_state`) and auth cookie (`session`) have different names | IMPLEMENTED |
| NFR-002 | Security: agent tool safety | No code-execution or free-form SQL tools / the usage tool is limited to the requester's own data / instructions inside tool results are ignored (system prompt) | IMPLEMENTED |
| NFR-003 | Cost cap | Completion token cap 1024 per turn (server-enforced) / agent graph step cap 20 | IMPLEMENTED |
| NFR-004 | Error exposure | Clients get only `{"detail": message}`; internal details go to logs only | IMPLEMENTED |
| NFR-005 | Observability | Every API call logged + `api_call_id` correlation / per-turn token usage log / tool call log / Langfuse tracing (with keys) | IMPLEMENTED |
| NFR-006 | RAG quality bar | eval: document precision ≥ `MIN_PRECISION`, judge score ≥ `MIN_JUDGE_SCORE` (thresholds in [LLM_SPECIFICATION.md](LLM_SPECIFICATION.md#evaluation-and-performance-criteria)) | IMPLEMENTED |

## New requirements

| ID | Requirement | AC | Status | Requested |
|---|---|---|---|---|
| FR-009 | Locust load-test environment + selectable scenarios + scenario doc | (1) `loadtest/` is a standalone uv project, run with `uv run locust -f locustfile.py` from `loadtest/` (2) env `LOADTEST_SCENARIO` selects smoke/load/stress/spike/soak/breakpoint, default smoke; an invalid value fails immediately with the list of valid values (3) `loadtest/SCENARIOS.md` describes each scenario's purpose, stage table, user mix, pass criteria (SLO), and rationale, with web source links (4) a run guide exists (mock server, backend env, locust command) (5) no real OpenAI billing: the mock serves chat + embeddings and the guide uses a dummy key (6) OAuth bypass: seed N users and sessions at start, delete the sessions at the end (7) chat responses are checked beyond 200 (content non-empty; citations non-empty in pinned mode) (8) smoke run against the real stack with 0 failures, or the reason it wasn't run is recorded | VERIFIED | 2026-11-14 |
| NFR-007 | Load tests don't change app code | 0 changes in `backend/app`, `frontend/` (the backend points at the mock via env `OPENAI_BASE_URL`) | VERIFIED | 2026-11-14 |

## Change history

| Date | Change | Approved by |
|---|---|---|
| 2026-11-14 | Harness adopted; baseline FR-001–008 / NFR-001–006 written (reverse-documented from code) | user (harness setup request) |
| 2026-11-14 | FR-009, NFR-007 added (Locust load-test environment) | user (via the main session) |
| 2026-11-14 | FR-009, NFR-007 → VERIFIED (T-002–T-007, CR-002, smoke run) | pm (evidence-based) |
