# Load test results (T-026, FR-009)

Date: 2026-11-14 (KST). Raw output: `loadtest/reports/{smoke,load}*` (gitignored). Every number below is from those CSVs/logs or from the sampler noted in section 5.

## 1. Environment

- Machine: Apple M2 (8 cores), 16 GB RAM, macOS (arm64). Everything shares this one machine: Docker infra, backend, ingest worker, mock, Locust.
- Infra: `docker compose -f system-docker-compose.yaml up -d` (postgres, redis, qdrant, kafka, kafka_ui, redis_insight), fresh empty volumes.
- Backend: host `uvicorn main:app --port 8000`, single process, real fastembed `intfloat/multilingual-e5-large` for query embedding. LLM = `loadtest/mock_openai.py` on :9000 (default latency, 2 calls/turn). `service-docker-compose.yaml` was NOT started.
- Prerequisite data: `rag_eval_papers` created via `POST /collections` (e5-large, dense 1024 + sparse BM25, description set). The 3 PDFs in `eval/test-data/` were converted with `pdftotext` and sent through `POST /collections/rag_eval_papers/documents` (the API takes text, not PDF). `uv run python -m workers.ingest_worker` ran with the mock env. All 3 documents reached INDEXED in about 100 s (e5 model was already in the local cache). No OpenAI call was involved: e5 is local and the mock env was set for every backend process.
- Prometheus/Grafana: not started (skipped to avoid adding load to the measurement). No target-UP evidence for T-009/T-018 from this run.

## 2. Commands

```bash
docker compose -f system-docker-compose.yaml up -d
(backend/app) uv run alembic upgrade head
(loadtest)    uv run python mock_openai.py
(backend/app) OPENAI_BASE_URL=http://localhost:9000/v1 OPENAI_API_KEY=sk-mock LANGFUSE_PUBLIC_KEY= LANGFUSE_SECRET_KEY= uv run uvicorn main:app --port 8000
(backend/app) same env, uv run python -m workers.ingest_worker
(loadtest)    set -a; . <(grep '^POSTGRES_' ../docker.env); set +a
              LOADTEST_SCENARIO=smoke uv run locust -f locustfile.py --headless --host http://localhost:8000 --csv reports/smoke
              LOADTEST_SCENARIO=load  uv run locust -f locustfile.py --headless --host http://localhost:8000 --csv reports/load --csv-full-history
```

Collection/document seeding script (session seeded straight in Postgres, deleted afterwards) was a scratch script, not committed.

## 3. Results

| Scenario | Duration | Requests | Failures | RPS (agg) | Exit code | Gate (SCENARIOS.md section 5) |
|---|---|---|---|---|---|---|
| smoke | 2 min, 3 users | 92 (CSV) / 93 (console final table) | 0 | 0.77 | 0 | PASS: fail 0, chat turns 22 >= 2, chat p95 2300 ms <= 3000 |
| load | 35 min, T=50 | 22,367 | 9 (0.04%) | 10.65 | 1 | FAIL: chat p95 3900 ms > 3000 ms (fail ratio 0.04% <= 1% would pass) |

The CSV and the console table differ by one request in smoke (one in-flight request counted at shutdown). The gate log line says `chat_turns=22, chat_p95=2300ms, fail_ratio=0.0000`.

### 3.1 smoke, per endpoint (ms)

| Endpoint | n | fail | p50 | p95 | p99 |
|---|---|---|---|---|---|
| GET /auth/me | 9 | 0 | 20 | 53 | 53 |
| POST /chats | 9 | 0 | 18 | 21 | 21 |
| POST /chats/[id]/messages | 22 | 0 | 1700 | 2300 | 2600 |
| GET /collections | 21 | 0 | 20 | 36 | 55 |
| GET /collections/[name]/documents | 11 | 0 | 38 | 60 | 60 |
| GET /models | 9 | 0 | 8 | 12 | 12 |
| GET /usage/stats | 11 | 0 | 25 | 36 | 36 |
| Aggregated | 92 | 0 | 25 | 2100 | 2600 |

### 3.2 load, per endpoint (ms, whole run)

| Endpoint | n | fail | RPS | p50 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|
| GET /auth/me | 2435 | 2 | 1.16 | 15 | 290 | 1800 | 13625 |
| POST /chats | 2435 | 0 | 1.16 | 16 | 260 | 1200 | 7621 |
| POST /chats/[id]/messages | 7233 | 5 | 3.44 | 1900 | 3900 | 6600 | 14414 |
| GET /collections | 4238 | 1 | 2.02 | 16 | 320 | 1500 | 10009 |
| GET /collections/[name]/documents | 1796 | 0 | 0.86 | 30 | 450 | 1800 | 12534 |
| GET /models | 2435 | 0 | 1.16 | 7 | 170 | 810 | 3315 |
| GET /usage/stats | 1795 | 1 | 0.85 | 20 | 370 | 1800 | 12092 |
| Aggregated | 22367 | 9 | 10.65 | 29 | 2300 | 5000 | 14414 |

All 9 failures are `http 0` (connection-level, no HTTP status): 5 on chat messages, 2 on auth/me, 1 each on collections and usage/stats. `_exceptions.csv` is empty. The backend log has no ERROR lines; 8 WARNING lines are startup warnings only.

Non-chat p95 target (<= 500 ms, report-only): all endpoints met it over the whole run (max 450 ms, documents list).

### 3.3 load, time profile (aggregated rolling p95 from `load_stats_history.csv`, 50 users from about 5 min on)

- Steady state: rolling chat-dominated p95 is 1.9-2.4 s in most samples (median of the chat row's rolling p95: 2200 ms in 5-15 min, 2400 ms in 15-25 min, 2200 ms after 25 min). That matches the 2.3 s expectation in SCENARIOS.md section 5.
- Stalls: 206 of 2083 history samples (about 10%) had rolling p95 > 3500 ms, in 5 windows: 17:46:55-17:47:28 (max 8.3 s), 17:47:41-17:47:52 (5.0 s), 17:54:03-17:55:13 (6.8 s), 17:56:32-17:57:30 (14 s), 17:58:05-17:58:52 (7.1 s). RPS dropped from about 11-13 to 5-6 in these windows. Roughly 4 of the 35 minutes were affected; after 17:59 no stall appeared.
- These stalls alone push the whole-run chat p95 from about 2.3 s to 3.9 s and cause the gate failure. The 9 `http 0` failures at 17:53:50, 17:54:25, 17:57:13 etc. fall into or next to those windows; the ones at 18:05:08, 18:06:50 and 18:09:09 do not (cause unknown; the last one is at the shutdown).

## 4. Comparison with the previous smoke (2026-11-14, before the compose split)

| | Previous | This run |
|---|---|---|
| Requests | 94 | 92 (93 console) |
| Failures | 0 | 0 |
| Chat p95 | 2300 ms | 2300 ms |
| Chat turns | not recorded here | 22 |

Equivalent. The compose split (system-docker-compose.yaml) did not change smoke behaviour.

## 5. Bottleneck observations

Sampled once a minute during load (`ps` on the uvicorn process, `pg_stat_activity` count for the app DB):

- API process CPU swings between 19% and 451% (it is multi-threaded: the e5 query embedding runs in ONNX threads inside the API process). Peaks at 309%, 354%, 398%, 451% (17:54, 17:56, 18:02, 18:03). The stall windows at 17:54-17:58 coincide with the 309% and 354% samples. Not every high-CPU sample coincides with a stall (18:02-18:03 had 398-451% and no stall in the history), so the CPU link is circumstantial, not proven.
- API RSS stayed 1.18-1.48 GB for the whole run (no growth trend; the first sample 1.46 GB, the last under load 1.47 GB).
- Postgres connections to the app DB: 9-19 (limit in the plan: pool 5+10 = 15 per SCENARIOS.md section 5 soak note; 17-19 includes other sessions such as the sampler and Locust seed). No pool exhaustion error was logged.
- Locust, the mock, the Docker VM and the backend all share 8 cores, so some of the stalls may come from the load generator or the host rather than the API alone. This was not separated (no second machine, no profiler run).
- Relevant open hypotheses: KI-011 (e5 query embedding on API CPU) and KI-010 (DB connection held across LLM calls). This run does not confirm or reject H1; there was no pool-exhaustion symptom at T=50 with a 1.9 s mock.

## 6. Issues found

- KI-023: chat p95 gate fails at T=50 on this machine (3900 ms), caused by intermittent 5-14 s stalls rather than steady-state slowness (steady p95 about 2.2 s).
- KI-024: 9 `http 0` failures during load with no server-side error log, so the cause is unexplained.
- No product bug found in smoke: citations and mock answers validated on all 22 chat turns.

## 7. Not run

stress, soak, spike, breakpoint (out of scope for T-026). Prometheus/Grafana (skipped). A repeat of load to see whether the stalls recur was not done. Real-LLM latency is not measured by design.
