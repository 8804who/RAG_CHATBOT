# Task Board

> Owner: `pm` only ([HANDOFF_PROTOCOL.md §2](HANDOFF_PROTOCOL.md#2-document-ownership-matrix)). Status rules and quality gates: [§5](HANDOFF_PROTOCOL.md#5-task-status).
> **Cells hold the latest result only.** Overwrite on each update; history lives in `AGENT_WORKLOG.md` and `archive/`.

Status: `NOT_STARTED` · `IN_PROGRESS` · `BLOCKED` · `REVIEW_REQUIRED` · `REVISION_REQUIRED` · `QA_REQUIRED` · `VERIFY_BLOCKED` (env reason named) · `COMPLETED`
Priority: `P0` (urgent/blocking) · `P1` (current scope) · `P2` (later)

## Active tasks

| Task ID | Task | Owner | Priority | Depends on | Acceptance criteria | Status | Latest result | Related |
|---|---|---|---|---|---|---|---|---|
| T-002 | OpenAI-compatible mock server (`loadtest/mock_openai.py`) | main session (built outside the harness, adopted later) | P1 | — | FR-009 (5): chat tool_call→answer in 2 steps, usage returned, embedding dims match, stream rejected | COMPLETED | CR-002 PASS_WITH_NOTES; PM re-ran ruff + `selfcheck.py` OK; smoke 94 req / 0 fail / chat p95 2300ms | FR-009, KI-013, KI-014 |
| T-003 | Load-test scenario design `loadtest/SCENARIOS.md` + decision | `system-architect` | P1 | — | FR-009 (2)(3)(7): stage tables, SLOs, bottleneck hypotheses, sources | COMPLETED | PM checked: 12 sources, 6 scenario stage tables, breakpoint stop rule, H1–H3; ramp rationale corrected in D-011 (T-006) | FR-009 |
| T-004 | `loadtest/locustfile.py` + `loadtest/README.md` + mock docstring + smoke run | `backend-developer` | P1 | T-003 | FR-009 (1)(2)(4)(5)(6)(7)(8), NFR-007 | COMPLETED | CR-002 PASS_WITH_NOTES; PM re-ran ruff + `selfcheck.py` OK; smoke 94 req / 0 fail | FR-009, KI-013, KI-014 |
| T-005 | Code review of T-002 + T-004 | `backend-code-reviewer` | P1 | T-004 | Review PASS or PASS_WITH_NOTES | COMPLETED | CR-002 PASS_WITH_NOTES (CR-001 #1–#8 resolved). Reviewer set COMPLETED itself; PM approved from CR-002 | FR-009 |
| T-006 | Correct SCENARIOS.md §4 / D-010(e) rationale + package layout | `system-architect` | P2 | T-004 | Wrong "start() blocks" rationale fixed, layout refs updated | COMPLETED | PM checked SCENARIOS.md lines 3, 68, §5; D-011 added. Docs only | FR-009 |
| T-007 | SCENARIOS.md §4/§4.6: `(0,100)` before seeding ends; `-t` and grace clock start after seeding | `system-architect` | P2 | T-004 revision | Lines 68, 70, 147 updated | COMPLETED | PM checked against `scenario.py:75-80`. Docs only | FR-009, CR-001 #2 |
| T-008 | Monitoring stack design: scrape targets, network, pinned versions, backend-metrics scope | `system-architect` | P1 | — | Decision (D-xxx) + spec for the implementation brief | COMPLETED | D-012, accepted by PM. Docs only | D-012 |
| T-009 | `monitoring-docker-compose.yaml` + `monitoring/**` (Prometheus, Grafana provisioning, exporters) | `backend-developer` | P1 | T-008 | `docker compose config` passes, no hardcoded secrets, pinned images | COMPLETED | CR-003 + revision re-reviewed in CR-005 (PASS_WITH_NOTES). PM: config exit 0. promtool / image pull not run (daemon down) | KI-015, KI-016, KI-017 |
| T-010 | Review T-009 | `backend-code-reviewer` | P1 | T-009 | PASS or PASS_WITH_NOTES | COMPLETED | CR-003 PASS_WITH_NOTES (static) | KI-015, KI-016, KI-017 |
| T-011 | Backend containerization + `api`/`frontend` services in the old `docker-compose.yaml` | `backend-developer` | P1 | — | Non-root, config passes, no secrets in image | COMPLETED | Superseded by T-020 (user changed the shape: system/service compose split) | |
| T-012 | Frontend containerization: `frontend/Dockerfile` (build → nginx-unprivileged), nginx `/api` proxy + SPA fallback | `frontend-developer` | P1 | — | Non-root, listens on 8080, `npm run build` passes | VERIFY_BLOCKED | CR-004 PASS_WITH_NOTES (static); `npm run build` passed. Waiting on: docker daemon down (`docker build`, run) | KI-019 |
| T-013 | Review T-015 + T-009 revision | `backend-code-reviewer` | P1 | T-015 | PASS or PASS_WITH_NOTES | COMPLETED | CR-005 PASS_WITH_NOTES | KI-015, KI-020, KI-021 |
| T-014 | Review T-012 | `frontend-code-reviewer` | P1 | T-012 | PASS or PASS_WITH_NOTES | COMPLETED | CR-004 PASS_WITH_NOTES | KI-018, KI-019 |
| T-015 | FastAPI `/metrics` + Prometheus `api` job; `LOG_INFRA_ENDPOINTS` log filter (user add-on) | `backend-developer` | P1 | — | `/metrics` exposed, tests pass, ruff clean, config passes | COMPLETED | CR-005 + CR-006 PASS_WITH_NOTES; PM re-ran pytest 100 passed / 2 failed (pre-existing `test_model_registry.py`), ruff clean. Live scrape not run | KI-020, KI-021 |
| T-016 | Frontend (nginx) monitoring | unassigned | P2 | T-012, T-020 | Pending scope answer | BLOCKED | Scope undecided by the user: nginx metrics (stub_status + exporter) vs browser RUM (contract change) | |
| T-017 | Re-review T-015 add-on (`LOG_INFRA_ENDPOINTS`) | `backend-code-reviewer` | P1 | T-015 | PASS or PASS_WITH_NOTES | COMPLETED | CR-006 PASS_WITH_NOTES (`/` also dropped from access log; no negative-case tests) | |
| T-018 | Loki + Grafana Alloy (container logs) + Grafana Loki datasource | `backend-developer` | P1 | T-009 | config passes, pinned images, Loki datasource provisioned | COMPLETED | CR-007 PASS_WITH_NOTES; PM: config exit 0. `loki -verify-config` / `alloy fmt` not run (daemon down) | KI-022 |
| T-019 | Review T-018 | `backend-code-reviewer` | P1 | T-018 | PASS or PASS_WITH_NOTES | COMPLETED | CR-007 PASS_WITH_NOTES | KI-022 |
| T-020 | Compose split: `system-docker-compose.yaml` (infra, `name: rag_chatbot_system`) + `service-docker-compose.yaml` (api, frontend, ingest-worker), non-root backend image, `LOG_INFRA_ENDPOINTS` in `.env`, doc refs | `backend-developer` | P1 | T-012 | All three compose files pass config; non-root | VERIFY_BLOCKED | CR-009 + CR-010 PASS_WITH_NOTES; PM: all three configs exit 0. Waiting on: docker daemon down (image build, startup smoke) | D-013 |
| T-021 | KI-018 nginx resolver fix | `frontend-developer` | P1 | T-012 | `resolver 127.0.0.11` + variable `proxy_pass`; `npm run build` passes | VERIFY_BLOCKED | CR-008 PASS_WITH_NOTES; build passed. Waiting on: docker daemon down (`nginx -t`, recovery smoke) | KI-018 |
| T-022 | Review T-020 | `backend-code-reviewer` | P1 | T-020 | PASS or PASS_WITH_NOTES | COMPLETED | CR-009 PASS_WITH_NOTES | |
| T-023 | Review T-021 | `frontend-code-reviewer` | P1 | T-021 | PASS or PASS_WITH_NOTES | COMPLETED | CR-008 PASS_WITH_NOTES | |
| T-024 | Review T-020 revision (`rag_chatbot_system`, network, compileall) | `backend-code-reviewer` | P1 | T-020 | PASS or PASS_WITH_NOTES | COMPLETED | CR-010 PASS_WITH_NOTES (if the first build fails, add `-x '/\.venv/'` to compileall) | |
| T-026 | Run load test (smoke → load) on fresh Docker stack, write `loadtest/RESULTS.md` | `qa-engineer` (main session delegated directly) | P1 | T-020 | Report with real numbers vs SCENARIOS.md §5 gates; mock LLM only | COMPLETED | QA-001 PARTIAL: smoke PASS exit 0 (92 req/0 fail/chat p95 2300 ms); load FAIL exit 1 (22,367 req/9 fail/chat p95 3900 ms > 3000). Main session checked RESULTS.md numbers. Open: KI-023, KI-024 | FR-009, QA-001 |
| T-027 | Run RAG eval baseline + add results export to `eval/` (dated JSON+MD with run metadata) + cost/latency findings | `rag-llm-engineer` | P1 | — | `eval/results/2026-11-21-baseline.{json,md}` with date, git sha, chat/embedding model, top_k, dataset size, per-case + aggregate metrics; `npm run typecheck` passes | COMPLETED | PM: `npx tsc --noEmit` OK, results r1/r2 present with full meta, not gitignored. 0/9 pass (stale golden doc ids), judge 0.911/0.944, p95 10.8/11.2 s | KI-004, KI-005 |
| T-028 | Diagnose retriever/embedding/answer quality from T-027 evidence + code; write `docs/RAG_IMPROVEMENT_PLAN.md` | `rag-llm-scientist` | P1 | T-027 | Baseline numbers, problems with file:line/metric evidence, ranked improvements (retriever/embedding/chatbot) with expected gain + how to measure, re-run/compare section | COMPLETED | PM checked: doc has §1 baseline, §2 problems P1-P19 w/ file:line, §3 ranked fixes, §4 order, §5 re-run; spot-checked `tools.py:23,34`, `agent_orchestrator.py:182-183`. Probe saved to `eval/results/2026-11-21-probe/` (py_compile OK) | KI-004 |
| T-025 | Harness upkeep: version the harness, ownership SSOT, agent tool allowlists, infra rules, `VERIFY_BLOCKED`, latest-only cells, English agent docs, worklog `Cost:` line | `pm` | P1 | — | `archive_logs.py --dry-run` clean, no doc contradicts §2, every agent has `tools:` | COMPLETED | PM: dry-run clean, grep checks below in worklog. Docs/config only (T0) | D-014 |
| T-029 | Eval v2 data: sourced non-paper docs (`eval/test-data/v2/`) + 5 datasets ko-rag/en-rag/ko-nonrag/en-nonrag/tool (`eval/fixtures/v2/`) with source URLs | `rag-llm-scientist` | P1 | T-028 | Every fact traceable to a fetched URL; sizes ~30/30/15/15/20; schema per T-030 | COMPLETED | PM: 5 files load, counts 30/30/15/15/20, 10 docs with Source headers | KI-025, KI-026 |
| T-030 | Eval v2 harness: resolve ids by title, retrieved doc/chunk recording + recall/precision, stronger judge w/ context (correctness + groundedness), non-RAG + tool assertions, tool sequence in results, `EVAL_DATASET` | `rag-llm-engineer` | P1 | — | `npx tsc --noEmit` passes; results JSON/MD carry dataset + tool sequence per case | COMPLETED | PM: tsc OK, unit 3/3; full 110-case run done in T-031, 0 errored. Merged PR #7 | KI-025, KI-026 |
| T-031 | Ingest v2 docs into `rag_eval_v2`, run full v2 baseline, update eval/README + RAG_IMPROVEMENT_PLAN §3.1/§5 | `rag-llm-engineer` | P1 | T-029, T-030 | `eval/results/2026-11-21-baseline-v2.{json,md}` with all cases | COMPLETED | PM: 110/110 case records, 36 pass; rag_eval_v2 10/10 INDEXED. Merged PR #8; plan §0/§1.1/§2 P20-P23/§4 updated | KI-025, KI-026 |

## Skipped phases

| Task ID | Skipped phase | Reason | What was actually verified |
|---|---|---|---|
| T-002~T-005 | Complexity: T2 (new standalone tool + load/concurrency design); no app layer or contract change | — | — |
| T-002~T-005 | `qa-engineer` | No UI or app behavior change (NFR-007); integration covered by the T-004 smoke run + PM re-run | T-004 smoke results |
| T-002~T-005 | `ux-designer`, `frontend-*`, `rag-llm-*` | No UI; LLM replaced by a mock; not a quality question | — |
| T-003 | `system-architect` final consistency check | No app architecture change; PM compared stage tables with the code | PM comparison |
| T-008~T-010 | Complexity: T2 (new infra component → architect trigger); no app contract change | — | — |
| T-008~T-010 | `qa-engineer`, `ux-designer`, `frontend-*`, `rag-llm-*` | No UI or app behavior change; no LLM path change | compose config + review |
| T-011~T-014 | Complexity: T2 (BE + FE, deployment config change, no API contract change) | — | — |
| T-011~T-014 | `system-architect` | No new infra component (containerizing existing services), no contract change; PM defaults stated in the briefs | 2 reviews |
| T-011~T-014, T-020~T-021 | `qa-engineer` | Docker daemon down: no image build or E2E possible → `VERIFY_BLOCKED`, user smoke steps provided | config + reviews |
| T-018~T-019 | `system-architect` | Extension of the stack accepted in D-012 (log backend), no app code or contract change; Alloy over EOL Promtail is a PM default | review |
| T-027~T-028 | Complexity: T2 (LLM-path quality question + eval tooling change; no backend/frontend app code, no contract change) | — | — |
| T-027~T-028 | `backend-code-reviewer`, `frontend-code-reviewer` | Only `eval/` TS tooling changes (not app code); no matching reviewer | PM runs `npm run typecheck` and inspects the diff |
| T-027~T-028 | `system-architect`, `ux-designer`, `qa-engineer`, `backend-developer`, `frontend-developer` | Research + measurement only; no architecture, UI, or app behavior change | — |
| T-025 | all specialists | T0: harness/config docs only; done by `pm` per the user's instruction | dry-run + grep checks |
| T-029~T-031 | Complexity: T2 (eval tooling + new test data; LLM-path quality measurement; user add-on: tool-calling dataset). No backend/frontend app code, no contract change | — | — |
| T-029~T-031 | `backend-code-reviewer`, `frontend-code-reviewer` | `eval/` TS tooling only, no matching reviewer (same as T-027) | PM runs `npx tsc --noEmit` and reviews the diff |
| T-029~T-031 | `system-architect`, `ux-designer`, `qa-engineer`, `backend-developer`, `frontend-developer` | No architecture, UI, or app behavior change | — |

## Completed outside the board flow

| Task ID | Task | Owner | Completed | Evidence |
|---|---|---|---|---|
| T-001 | Build the multi-agent harness docs and wire the agents | main session (before the harness, not via PM) | 2026-11-14 | Link and agent-name check script (see worklog). No code change → no review/QA gate |
