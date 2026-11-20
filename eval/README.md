# RAG Eval (Playwright)

Data-driven precision / token-usage / latency checks against the real chat
API (`POST /api/v1/chats`, `POST /api/v1/chats/{id}/messages`) and Postgres —
API-level only, no browser, no mocking.

## What it measures, per question in `fixtures/golden-dataset.json`

- **Precision** — `citations[].document_id` returned vs. `expectedDocumentIds`
  you provide. Always asserted (`minPrecision`, default 0.3, overridable per
  case or via `MIN_PRECISION` — see the corpus-size note below before raising
  this).
- **Answer correctness (LLM-as-judge)** — an OpenAI model (`src/judge.ts`,
  default `gpt-4o-mini`, override with `JUDGE_MODEL`) grades the chatbot's
  actual answer against each case's `expectedAnswer` on a 0.0–1.0 scale via
  a structured-output call, tolerant of paraphrasing but strict on facts and
  numbers. Always asserted (`minJudgeScore`, default 0.6, overridable per
  case or via `MIN_JUDGE_SCORE`). Uses its own `OPENAI_API_KEY` in `eval/.env`
  (can be the same key as `backend/app/.env` or a different one) — this is
  extra OpenAI spend on top of the chat model calls themselves.
- **Token usage** — read directly from `chat_usage_logs` (input/output/
  reasoning), keyed by `conversation_id = chat_id` — the aggregated
  `/usage/stats` endpoint sums across all messages for a model, so it can't
  isolate one query. Only asserted if a case sets `maxTotalTokens`. (The
  judge call's own token usage is not tracked here — only the chat model's.)
- **Time** — wall-clock around `POST /messages`. Only asserted if a case sets
  `maxElapsedMs`.

All four are always recorded and printed in a summary table at the end of
the run, and attached per-test as JSON (including the judge's reasoning and
the chatbot's actual answer) in the HTML report, even when not asserted.

## Prerequisites

1. Infra + backend running per the repo root `CLAUDE.md` (`docker compose -f
   system-docker-compose.yaml up -d`, `uv run alembic upgrade head`, then `uv run uvicorn main:app --port
   8000` from `backend/app`). Ingest workers aren't needed to *run* this
   suite, only to have ingested your eval documents beforehand.
2. A Qdrant collection with your eval documents already ingested (via the
   existing `/collections` + `/documents` API), and each question's real
   `document_id`s filled into `fixtures/golden-dataset.json`.
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
That's exactly the current `rag_eval_papers` collection (Transformer=7,
BERT=5, GPT=5 chunks) — `MIN_PRECISION=0.3` is calibrated to that ceiling,
not to weak retrieval. It still catches genuine zero-precision misses (the
correct paper not appearing at all). Ingest more/larger documents (or raise
`DEFAULT_RETRIEVAL_TOP_K`'s relevance vs. corpus size) before tightening
this threshold.

## Run

```bash
cd eval
npm install
npm test
npm run test:report   # open the HTML report
```

## Editing the dataset

Each entry in `fixtures/golden-dataset.json`:

|field|required|meaning|
|---|---|---|
|`id`|yes|test name suffix|
|`query`|yes|question sent to the chat|
|`collectionName`|yes|must already be ingested|
|`chatModel`|yes|must be a registered chat model (`GET /api/v1/models`)|
|`expectedDocumentIds`|yes|golden relevant `document_id`s, for precision|
|`expectedAnswer`|yes|reference answer the LLM judge grades against|
|`minPrecision`|no|overrides `MIN_PRECISION` for this case|
|`minJudgeScore`|no|overrides `MIN_JUDGE_SCORE` for this case|
|`maxElapsedMs`|no|latency budget; unset = record only|
|`maxTotalTokens`|no|token budget; unset = record only|

The current dataset (`fixtures/golden-dataset.json`) is built from the three
papers in `test-data/` (Transformer, BERT, GPT), ingested into a
`rag_eval_papers` collection (fastembed `intfloat/multilingual-e5-large`,
hybrid dense+sparse) — 9 cases, 3 per paper, each targeting one paper's
`document_id`.
