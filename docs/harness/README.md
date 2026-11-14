# Harness — multi-agent collaboration system

This directory is the **single source of truth** shared by every agent in this project (PM + 9 specialist subagents) and the main session.
Agents can't see each other's conversations. Anything that must be shared is written down here.

> The detailed collaboration rules (before/during/after work, handoff format, task status, conflict prevention) are canonical in **[HANDOFF_PROTOCOL.md](HANDOFF_PROTOCOL.md)**. This README is only the entry point. Document ownership is defined once, in [HANDOFF_PROTOCOL.md §2](HANDOFF_PROTOCOL.md#2-document-ownership-matrix).

## Document map

| Document | Contents |
|---|---|
| [README.md](README.md) | Entry point, document map, workflow |
| [HANDOFF_PROTOCOL.md](HANDOFF_PROTOCOL.md) | Collaboration, handoff, status, ownership, and conflict rules (canonical) |
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | Purpose, features, stack, directories, domain, development stage |
| [REQUIREMENTS.md](REQUIREMENTS.md) | Requirements, acceptance criteria, change history |
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | System structure, dependencies, data flow, principles |
| [API_CONTRACTS.md](API_CONTRACTS.md) | API spec, auth, errors, FE↔BE contract |
| [DESIGN_GUIDELINES.md](DESIGN_GUIDELINES.md) | Design system, tokens, components, accessibility |
| [LLM_SPECIFICATION.md](LLM_SPECIFICATION.md) | Models, RAG, agent, prompts, evaluation criteria |
| [TASK_BOARD.md](TASK_BOARD.md) | Tasks, owners, status, dependencies, acceptance criteria |
| [AGENT_WORKLOG.md](AGENT_WORKLOG.md) | Per-agent work records (append-only) |
| [DECISION_LOG.md](DECISION_LOG.md) | Technical decisions and rationale |
| [CODE_REVIEW_LOG.md](CODE_REVIEW_LOG.md) | Code review results |
| [QA_REPORT.md](QA_REPORT.md) | Test scenarios, results, regressions |
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | Open bugs, tech debt, risks |
| `archive/` | Worklog and review entries of `COMPLETED` tasks, moved by `archive_logs.py`. Grep by ID; not translated (history) |

Who edits each document: [HANDOFF_PROTOCOL.md §2](HANDOFF_PROTOCOL.md#2-document-ownership-matrix).

## Relation to existing docs (no duplication)

The harness **links to** existing docs rather than replacing them. The docs below are canonical for their topic; harness docs hold only summaries and links.

| Topic | Canonical source |
|---|---|
| Commands, key rules summary | [`/CLAUDE.md`](../../CLAUDE.md) |
| Code structure, request flows, architecture details | [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) |
| Coding, comment, test, log, and design rules | [`/.claude/.rules/`](../../.claude/.rules/) (`code.md`, `annotation.md`, `test_code.md`, `log.md`, `design.md`) |
| RAG/Kafka design rationale | [`docs/RAG_ARCHITECTURE.md`](../RAG_ARCHITECTURE.md), [`docs/KAFKA_INGESTION.md`](../KAFKA_INGESTION.md), [`docs/EMBEDDING_AND_COLLECTIONS.md`](../EMBEDDING_AND_COLLECTIONS.md) |
| RAG eval harness usage | [`eval/README.md`](../../eval/README.md) |
| Agent definitions | [`/.claude/agents/`](../../.claude/agents/) |

## Workflow

1. `pm` analyzes the request and checks the current context in these docs.
2. `pm` defines scope and acceptance criteria → `REQUIREMENTS.md`, `TASK_BOARD.md`.
3. If needed, `system-architect` reviews the design → `SYSTEM_ARCHITECTURE.md`, `API_CONTRACTS.md`, `DECISION_LOG.md`.
4. `pm` distributes tasks to specialist agents (independent tasks in parallel; overlapping file scopes in sequence).
5. Each agent updates the specialty docs it owns and reports back. `pm` updates `TASK_BOARD.md` and `AGENT_WORKLOG.md` from the report ([§2](HANDOFF_PROTOCOL.md#2-document-ownership-matrix)).
6. Code changes are checked by the matching code reviewer → `CODE_REVIEW_LOG.md`.
7. Integrated features are checked by `qa-engineer` → `QA_REPORT.md`.
8. `pm` checks the results and doc consistency, then reports to the user.

Small work may skip phases, but the skipped phases, the reason, and what was actually verified go on `TASK_BOARD.md`.
Plain questions and explanations need no agents and no doc updates.

## Priority on conflict

1. The user's explicit request
2. Existing project requirements and policies (`CLAUDE.md`, `.claude/.rules/`, `REQUIREMENTS.md`)
3. `SYSTEM_ARCHITECTURE.md`
4. `DECISION_LOG.md`
5. Other specialty docs
6. The current task instruction

Don't decide conflicts on your own. `pm` identifies the conflict and checks with the user or the document owner.

## How to run

- PM drives the whole harness: `claude --agent pm` (PM is the main thread, can call only the 9 agents, and can ask the user directly).
- Normal session: following the Harness rules in `CLAUDE.md`, the main session delegates development requests to `pm`, or sends small work straight to the matching specialist.
