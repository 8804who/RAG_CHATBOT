# Handoff Protocol — canonical rules for agent collaboration

Every agent (the main session included) follows these rules for development, design, research, review, and testing work.
Agent definition files (`.claude/agents/*.md`) only link here; the rules live in this document alone.

Agent-facing docs (docs/harness/, .claude/) are written in English; code comments/docstrings stay Korean per .claude/.rules/.

---

## 1. Before working

**Subagents:** the delegation brief (§6) is your only context. Read only the files and docs the brief names, plus the code you will change. Don't browse `docs/harness/` on your own or re-read `CLAUDE.md` (it's already in context). If the brief lacks something you need, look up only that fact or ask `pm`.

**`pm` (including the main session acting as pm):**
1. If the work needs runtime checks (build, run, E2E, scrape), check the environment first (`docker info`, required services). Plan around anything that's down.
2. Read `TASK_BOARD.md`, `KNOWN_ISSUES.md`, `DECISION_LOG.md`, and the specialty docs the request touches.
3. Don't read the append-only logs (`AGENT_WORKLOG.md`, `CODE_REVIEW_LOG.md`) whole; grep them by Task ID or file name.
4. Check whether the planned change conflicts with the existing design, API contracts, or decisions. If it does, report it before starting (§8).
5. Put only the facts the agent needs into the brief. Don't re-argue settled decisions.

## 2. Document ownership matrix

This section is the single source of truth for who edits what. Other docs link here instead of restating it.

Each agent **edits only the documents it owns**. Errors in other documents are not fixed directly; pass them to the owner (in your report, or as a `KNOWN_ISSUES.md` entry).
**`TASK_BOARD.md` and `AGENT_WORKLOG.md` are edited by `pm` only** (or by the main session when it delegates to a specialist directly, acting as pm). Subagents never edit them. `pm` updates the status and appends the entry from each agent's report.

| Agent | Owns (edits) | Mainly reads |
|---|---|---|
| `pm` | PROJECT_CONTEXT, REQUIREMENTS, TASK_BOARD, AGENT_WORKLOG, HANDOFF_PROTOCOL, README, KNOWN_ISSUES (status column), DECISION_LOG (user decisions only) | everything |
| `system-architect` | SYSTEM_ARCHITECTURE, API_CONTRACTS, DECISION_LOG | REQUIREMENTS, LLM_SPECIFICATION, KNOWN_ISSUES |
| `backend-developer` | API_CONTRACTS (keep in sync with the implementation) | SYSTEM_ARCHITECTURE, DECISION_LOG, CODE_REVIEW_LOG |
| `backend-code-reviewer` | CODE_REVIEW_LOG, KNOWN_ISSUES | API_CONTRACTS, SYSTEM_ARCHITECTURE, DECISION_LOG |
| `frontend-developer` | DESIGN_GUIDELINES (keep in sync with the implementation), API_CONTRACTS (FE types) | DESIGN_GUIDELINES, API_CONTRACTS, CODE_REVIEW_LOG |
| `frontend-code-reviewer` | CODE_REVIEW_LOG, KNOWN_ISSUES | DESIGN_GUIDELINES, API_CONTRACTS |
| `qa-engineer` | QA_REPORT, KNOWN_ISSUES | REQUIREMENTS (AC), API_CONTRACTS, DESIGN_GUIDELINES |
| `rag-llm-scientist` | LLM_SPECIFICATION (research and selection rationale), DECISION_LOG (LLM decisions) | SYSTEM_ARCHITECTURE, QA_REPORT |
| `rag-llm-engineer` | LLM_SPECIFICATION (actual implementation, config, performance) | DECISION_LOG, SYSTEM_ARCHITECTURE |
| `ux-designer` | DESIGN_GUIDELINES | REQUIREMENTS, QA_REPORT (UX issues) |

Shared docs (API_CONTRACTS, DESIGN_GUIDELINES, LLM_SPECIFICATION) mark an owner per section. Edit only your own sections.

## 3. During work

- Follow `CLAUDE.md` and `.claude/.rules/*.md`.
- Don't edit outside the brief's "Edit" scope. If you need to, stop and report.
- Don't change contracts in `API_CONTRACTS.md` (paths, request/response shapes, status codes, errors) on your own. A change needs `system-architect` approval → a `DECISION_LOG.md` entry → handoff to both BE and FE (§7).
- Record anything other agents must know (bugs, hidden dependencies, behavior that differs from the docs) right away, in the doc you own or in `KNOWN_ISSUES.md`.

## 4. After working

Subagents do 1–3 below and return a report (§6). `pm` receives the report and does 4–5.

1. Owned specialty docs: reflect only the facts your work changed.
2. If you made a technical decision, record it in `DECISION_LOG.md`. If you don't own that log, put the decision in your report.
3. If you found a problem, add it to `KNOWN_ISSUES.md`. If you don't own that file, put it in your report.
4. (`pm`) `TASK_BOARD.md`: move the task row to its next status (§5). **A board cell holds the latest result only.** Overwrite the previous result; history belongs in `AGENT_WORKLOG.md` and `archive/`.
5. (`pm`) `AGENT_WORKLOG.md`: append one entry in the format below. Copy verification exactly as reported.

**Honest records:** never write that a test, review, or verification ran when it didn't. Record results as actual output (pass/fail counts, the command). Record failures and incomplete work as they are.

### AGENT_WORKLOG entry format

```markdown
### YYYY-MM-DD · <agent-name> · <Task ID>
- Work: one-line summary
- Files: path/to/file.py, ...
- Deliverables: (code, docs, report paths)
- Verification: commands run and results (e.g. `uv run pytest tests/...` → 12 passed), or "not run" with the reason
- Issues found: KI-xxx or "none"
- Follow-up: next owner and what to do, or "none"
- Cost: <subagent tokens> tokens / <tool uses> tool uses / <duration> — copied from the Agent tool result's usage; `n/a` if absent. Never estimate.
```

## 5. Task status

| Status | Meaning | Who moves it on |
|---|---|---|
| `NOT_STARTED` | Assigned, not started | `pm` |
| `IN_PROGRESS` | Being worked on | `pm` (from the agent's report) |
| `BLOCKED` | Waiting on a task, decision, or information (reason required) | `pm` |
| `REVIEW_REQUIRED` | Implementation done, waiting for code review | `pm` (from the reviewer's verdict) |
| `REVISION_REQUIRED` | Review or QA asked for changes | owning engineer → back to `REVIEW_REQUIRED` |
| `QA_REQUIRED` | Review passed, waiting for QA | `pm` (from the QA result) |
| `VERIFY_BLOCKED` | Review passed, but a required runtime check (build, run, E2E) can't run because of the environment. Name it, e.g. "docker daemon down" | `pm`, once the environment is back and the check has run |
| `COMPLETED` | All gates passed and docs updated | `pm` only |

`VERIFY_BLOCKED` is not `COMPLETED`. `archive_logs.py` archives only `COMPLETED` tasks, so these stay in the live logs.

**Quality gates (never skipped; if a phase is skipped, record the reason on TASK_BOARD):**
- Code change → `REVIEW_REQUIRED` when implementation is done. Engineers never set `COMPLETED` themselves.
- Backend code → `backend-code-reviewer`; frontend code → `frontend-code-reviewer`.
- User-visible features or BE·FE integration → after review, `QA_REQUIRED` → `qa-engineer`.
- Architecture or API contract changes → `system-architect` review.
- Infra config (compose, Dockerfiles, Prometheus/Loki/Alloy/nginx config) has no TDD. It is validated with the tool's own checker (`docker compose config`, `promtool check config`, `nginx -t`, `loki -verify-config`, `alloy fmt`) and still goes through code review.
- Docs-, design-, or research-only work has no review gate. `pm` checks the deliverable and sets `COMPLETED`.

## 6. Handoff format

This is the canonical brief template; `pm.md` and `CLAUDE.md` link here.

The brief is the subagent's **only context**, and every line costs tokens on every call. The receiver can't see the sender's conversation, so include every fact it needs and nothing it doesn't. Aim for ≤ 30 lines, in English.

```text
Task: T-xxx → <agent>
Goal: 1–2 sentences, and which acceptance criteria it serves.
Facts: only what this task needs, ≤ 10 bullets. Decisions as "D-xxx: one-line gist",
       contract shapes, KI-xxx, and for a revision the CR-xxx/QA-xxx id to fix.
Read: exact paths, ideally path:lines or a doc section. Nothing else is required reading.
Edit: allowed paths. Out of scope: …
Done when: commands that must pass, plus conditions.
```

- State the fact, not a pointer to a whole doc ("see DECISION_LOG" ✗ / "D-012: chat stays non-streaming" ✓).
- Don't forward earlier agents' full reports. Pass `file:line` and the `CR-`/`QA-` id only.
- Don't repeat what the agent definition already says (rules, report format, stack).

**Report format (receiver → `pm`, ≤ 15 lines, don't repeat the brief):** status, changed files (`file:line`), verification (actual commands and pass/fail counts), docs updated, open items and deviations from the brief. Reviewers and QA write details in their `CR-`/`QA-` entry; the report has only the verdict, the id, and one line per blocking item.

**Handoff is complete when** `pm` has updated `TASK_BOARD.md` and `AGENT_WORKLOG.md` from the report and confirmed the agent updated its owned docs. If it didn't, `pm` sends it back.

## 7. Conflict prevention and concurrency

1. **No two agents edit the same file at the same time.** Before parallel work, `pm` checks each task's edit scope and splits or serializes overlaps.
2. **Shared docs get partial edits only.** Don't `Write` (overwrite) a shared doc. Re-read it right before editing and `Edit` only your row or section. If `Edit` fails because the file changed, re-read and retry.
3. **Logs are append-only.** In `AGENT_WORKLOG`, `DECISION_LOG`, `CODE_REVIEW_LOG`, and `QA_REPORT`, don't edit existing entries; append new ones. To reverse a decision, write `Supersedes: D-xxx` in the new entry and change only the old entry's status to `Superseded by D-yyy`.
4. **IDs are the file's last ID + 1.** Re-read right before appending to pick the number (T-, D-, CR-, QA-, KI-, FR-, NFR-).
5. **When a technical decision changes, update the related docs together** (e.g. a model change → DECISION_LOG + LLM_SPECIFICATION + SYSTEM_ARCHITECTURE if needed).
6. **API or data-structure changes:** after `system-architect` approval, update `API_CONTRACTS.md` first, then assign separate `backend-developer` and `frontend-developer` tasks. Never set `COMPLETED` with only one side changed.
7. **When a design change affects implementation,** hand it to the engineer in the handoff format.
8. **Git:** follow the project policy. Commit or push only when the user asks.

## 8. Conflict resolution

1. When docs, docs and code, or agents disagree, **don't overwrite on your own.**
2. The agent that finds the conflict reports it to `pm` (which doc/file and section, and the evidence for each side).
3. `pm` checks whether the priority order ([README.md](README.md#priority-on-conflict)) settles it.
4. Technical conflict → `system-architect` decides from the evidence → `DECISION_LOG.md`.
5. Requirement or scope conflict → ask the user. `pm` never changes scope without user approval.
6. When code and docs disagree, **the current code is the fact.** The doc owner fixes the doc. If the code is wrong, add a `KNOWN_ISSUES.md` entry and create a fix task.
