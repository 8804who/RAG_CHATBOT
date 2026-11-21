# RAG Eval (Playwright)

Data-driven precision / token-usage / latency checks against the real chat
API (`POST /api/v1/chats`, `POST /api/v1/chats/{id}/messages`) and Postgres —
API-level only, no browser, no mocking.

## What it measures, per case in `fixtures/v2/<dataset>.json`

Datasets: `ko-rag`, `en-rag`, `ko-nonrag`, `en-nonrag`, `tool`. Pick with
`EVAL_DATASET` (comma list or `all`, default `all`); the selection is
recorded in the results meta.

- **Retrieval (RAG cases)** — `expectedDocumentTitles` (filenames) are resolved
  to `document_id`s at run start from `document_progress_status` (INDEXED rows,
  within `collectionName` if set). An unresolved or ambiguous title fails the
  case before any chat call — it never scores a silent 0. Per case the
  retrieved `document_id`s and `chunk_id`s are recorded; **citations are every
  chunk `search_documents` returned that turn** (deduped), not only the ones
  the answer cites (`_extract_citations` in `agent_orchestrator.py`).
  Document-level recall@k and precision are asserted for RAG cases
  (`expectedBehavior: answer_from_docs`, or no behavior with expected titles)
  against `minRecall` / `minPrecision` (defaults `MIN_RECALL=1`,
  `MIN_PRECISION=0.3`).
- **LLM-as-judge** — `src/judge.ts`, default `gpt-6.2-sol` (stronger than the
  `gpt-4o-mini` / `gpt-4o` chat models under test; override with
  `JUDGE_MODEL`). It sees the question, expected answer, actual answer and the
  retrieved citation snippets — the same 300-char chunk prefixes the agent
  saw — and returns **correctness** and **groundedness** separately
  (structured output). Correctness is asserted (`minJudgeScore`, default
  `MIN_JUDGE_SCORE=0.6`); groundedness is recorded only. Uses its own
  `OPENAI_API_KEY` in `eval/.env` — extra OpenAI spend on top of the chat calls.
- **Tools / behavior** — from `agent_tool_call_logs` (`conversation_id =
  chat_id`): `expectedTools` called, `forbiddenTools` not called,
  `expectedArgs` (`equals` compared as strings; `evaluatesTo` parses the
  arithmetic expression with a safe parser, no `eval()`), `maxToolCalls`.
  `no_search` ⇒ no `search_documents`; `web_search` ⇒ `tavily_search` or
  `arxiv_search`; `not_in_docs` ⇒ the answer has no `[n]` source markers
  (unless it used web search). The full tool sequence (name + args) is
  recorded for every case.
- **Token usage** — from `chat_usage_logs` (input/output/reasoning) for the
  chat model only (not the judge). Recorded, not asserted.
- **Time** — wall-clock around `POST /messages`. Recorded, not asserted.

Every run writes `results/<YYYY-MM-DD>-<EVAL_LABEL>.json` and `.md`
(`EVAL_LABEL` defaults to `baseline`; same date + label overwrites) via
`src/results-reporter.ts`: run metadata (git sha, datasets, chat/judge models,
citation semantics, top-k, chunking), a per-dataset aggregate table, every
case (metrics, behavior failures, tool sequence, judge reasoning, answers,
citations), and prints a summary table of all cases to the console.
`tests/metrics.unit.spec.ts` covers the pure metric/behavior logic and needs
no API (`npx playwright test tests/metrics.unit.spec.ts`).

## Prerequisites

1. Infra + backend running per the repo root `CLAUDE.md` (`docker compose -f
   system-docker-compose.yaml up -d`, `uv run alembic upgrade head`, then `uv run uvicorn main:app --port
   8000` from `backend/app`). Ingest workers aren't needed to *run* this
   suite, only to have ingested your eval documents beforehand.
2. The eval documents ingested under the filenames the fixtures name:
   `rag_eval_papers` (the 3 PDFs in `test-data/`, already ingested; never
   modify it) and `rag_eval_v2` (the 10 `test-data/v2/*.md`). For the latter
   run `npm run ingest:v2` with the API **and** the ingest worker up
   (`uv run python -m workers.ingest_worker`). `scripts/ingest-v2.ts` creates
   `rag_eval_v2` with `rag_eval_papers`' embedding config (if missing),
   uploads each `.md` via `POST /collections/rag_eval_v2/documents`, skips
   filenames already INDEXED or in flight (re-uploads FAILED-only ones), and
   waits until all 10 are INDEXED. Safe to re-run.
3. `cp .env.example .env` and fill in Postgres creds (defaults match the
   repo root `docker.env`) — used to seed a test session (bypassing Google
   OAuth) and to read back per-message token usage — plus `OPENAI_API_KEY`
   for the LLM judge.

Note: `RetrievalService` has no relevance-score cutoff — it always returns
the top `DEFAULT_RETRIEVAL_TOP_K` (8) nearest chunks, even for off-topic
questions. Don't write a golden case expecting zero citations.

**Precision ceiling vs. corpus size:** if every document in your collection
has fewer chunks than `DEFAULT_RETRIEVAL_TOP_K` (8), top-k retrieval can
*never* return chunks from only one document — at least two documents'
chunks always fill the top 8, capping best-case precision at 0.5, and it
drops further (e.g. 0.33) whenever a third document's chunk also surfaces.
That was the original `rag_eval_papers` ingest (Transformer=7, BERT=5,
GPT=5 chunks). Since the 2026-11-14 re-ingest it is Transformer=19, BERT=31,
GPT=19 chunks, so the ceiling no longer binds.
`rag_eval_v2` brings it back: 10 short docs make 15 chunks in total, so a
top-8 search for a single-document question spans about 7 documents. That
puts document precision near 1/7, below `MIN_PRECISION=0.3`, and v2 RAG
cases fail precision by construction. Keep this in mind when you read
`baseline-v2` pass counts.
`MIN_PRECISION=0.3` was calibrated to the old ceiling,
not to weak retrieval. It still catches genuine zero-precision misses (the
correct paper not appearing at all). Ingest more/larger documents (or raise
`DEFAULT_RETRIEVAL_TOP_K`'s relevance vs. corpus size) before tightening
this threshold.

## Run

```bash
cd eval
npm install
npm run ingest:v2                                  # once (idempotent)
EVAL_DATASET=all EVAL_LABEL=baseline-v2 npm test   # → results/<date>-baseline-v2.{json,md}
EVAL_DATASET=ko-rag,tool EVAL_LABEL=my-try npm test
npm run test:report   # open the HTML report
npm run typecheck
```

Current v2 baseline: `results/2026-11-21-baseline-v2.{json,md}` (110 cases).
`baseline-r1/r2` are the old 9-case golden set and are not comparable.

## Editing the dataset

Each `fixtures/v2/<dataset>.json` is an array of:

|field|required|meaning|
|---|---|---|
|`id`, `dataset`, `lang`|yes|case id, dataset name (file name wins), `ko`/`en`|
|`query`|yes|question sent to the chat|
|`collectionName`|yes|pinned collection, or `null` to let the agent route|
|`expectedDocumentTitles`|yes|filenames of the relevant documents (`[]` for non-RAG)|
|`expectedAnswer`|yes|reference answer the judge grades against|
|`sourceUrls`|yes|provenance of the expected answer|
|`expectedBehavior`|no|`answer_from_docs`, `no_search`, `web_search`, `not_in_docs`|
|`expectedTools` / `forbiddenTools`|no|tool names that must / must not be called|
|`expectedArgs`|no|`[{tool, arg, equals?, evaluatesTo?}]`|
|`maxToolCalls`|no|upper bound on tool calls this turn|
|`minJudgeScore` / `minRecall` / `minPrecision`|no|per-case threshold overrides|

The chat model comes from `CHAT_MODEL` (default `gpt-4o-mini`).
`EVAL_FIXTURES_DIR` points at another fixture directory (e.g. a scratch set).

`fixtures/golden-dataset.json` is **retired for the eval** (stale hard-coded
`document_id`s, KI-025). It stays only because `loadtest/` still reads its
queries.
