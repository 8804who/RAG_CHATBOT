# Code Review Log

> Owners: `backend-code-reviewer`, `frontend-code-reviewer` · append-only (new reviews go at the end).
> Problems not fixed right away also go in [KNOWN_ISSUES.md](KNOWN_ISSUES.md). The verdict goes in your report; `pm` moves the [TASK_BOARD.md](TASK_BOARD.md) row ([HANDOFF_PROTOCOL.md §2](HANDOFF_PROTOCOL.md#2-document-ownership-matrix)).

## Format

```markdown
### CR-xxx · YYYY-MM-DD · <reviewer> · <Task ID>
- Reviewed: branch / commit range / files
- Verdict: PASS | PASS_WITH_NOTES | CHANGES_REQUESTED
- Verification: commands run and results (e.g. `uv run pytest` → 120 passed, `npm run build` OK)

| # | Severity | Location (file:line) | Problem | Requested fix | Confidence | Handling |
|---|---|---|---|---|---|---|
| 1 | Critical/Major/Minor | | | | confirmed/plausible | fixed (CR-yyy) / KI-xxx / open |

- Re-review: (CR id of the re-review after the fix)
```

## Review records

### CR-004 · 2026-11-14 · frontend-code-reviewer · T-014 (reviews T-012)
- Reviewed: `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/.dockerignore` (+ references: `frontend/vite.config.ts`, `src/lib/config.ts`, `src/lib/api/client.ts`, `backend/app/api/v1/endpoints/documents.py`, `schemes/requests.py`, `main.py`)
- Verdict: PASS_WITH_NOTES
- Verification: careful reading and static reasoning only. With the Docker daemon down, `docker build`, `nginx -t`, image tag existence checks, and a real start were not run. The developer's `npm run build` pass was not re-run (no src change).

| # | Severity | Location | Problem | Requested fix | Confidence | Handling |
|---|---|---|---|---|---|---|
| 1 | Major | `nginx.conf:8` | `proxy_pass http://api:8000;` (literal host) resolves DNS once at nginx startup. (a) If `api` isn't on the network yet, nginx fails to start with `host not found in upstream`; (b) if only the `api` container restarts/recreates and its IP changes, nginx keeps the old IP and returns 502 until nginx restarts. `depends_on` only partly mitigates (a) (start order). | Use Docker's embedded DNS: `resolver 127.0.0.11 valid=10s;` + `set $api http://api:8000; proxy_pass $api;` (with a variable no URI part is appended, so `/api/...` passes through). Or accept (a) with compose `restart: unless-stopped`. | confirmed (nginx behavior, not run) | KI-018 |
| 2 | Minor | `nginx.conf:17` | `client_max_body_size 50m` has no basis. Backend upload is not multipart but a JSON body `IngestDocumentRequest{filename<=255, content: str}`; `content` has no `max_length` and uvicorn/FastAPI have no body-size limit either (`UploadFile`, 413 handling: 0 grep hits). So the nginx value is the only cap. No consistency conflict (the backend is more lenient), but 50m of JSON text affects the number of chunks to embed, memory, and Kafka message size. Over the limit nginx returns an HTML 413, and the frontend `apiFetch` may fail to parse it as a JSON error. | Value can stay (local). Set a backend `content` `max_length`/size policy and match nginx to it (`backend-developer`). Optionally an `error_page 413` JSON response. | confirmed (from backend code) | KI-019 |
| 3 | Minor | `nginx.conf` overall | No `gzip`. The image's default `nginx.conf` has `#gzip on;` commented out, so JS/CSS are served uncompressed. | `gzip on; gzip_types text/css application/javascript application/json image/svg+xml;` (server block) | plausible (from memory of the image default, not run) | open |
| 4 | Minor | `nginx.conf:9-12` | No `X-Forwarded-Host`. No impact today: Host is kept as `$http_host` (:5173) and the OAuth callback goes straight to 8000. If the backend starts building absolute URLs from `request.url`, it sees `localhost:5173` rather than `api:8000` because Host is preserved, so still fine. `proxy_read_timeout 300s` is enough for a non-streaming 30–60s chat (generous but harmless). | No action. Add proxy headers when needed. | confirmed | open |
| 5 | Minor | `Dockerfile:10-13` | No `HEALTHCHECK`; `Dockerfile`/`nginx.conf`/`.dockerignore` aren't in the build-context exclude list (only causes cache invalidation, not secrets). | `HEALTHCHECK CMD wget -qO- http://127.0.0.1:8080/ || exit 1` (optional). | confirmed | open |

Checked and fine (with reasons):
- Non-root correctness: `nginx-unprivileged` runs as uid 101 with pid and `client_body/proxy/fastcgi` temp paths under `/tmp`, so they're writable, and 8080 is unprivileged. The `COPY`'d `default.conf` and `dist` are root-owned 644/755, readable by uid 101 with no writes needed. Temp files for 50m uploads also go to `/tmp`. The image default already includes `conf.d/*.conf`, so overwriting `default.conf` works.
- `/metrics` not exposed: nginx handles only `/api/`, `/assets/`, `/index.html`, `/`; `/metrics` falls back to the SPA `index.html` (200) and isn't proxied to the backend. Note: if T-015 put `/metrics` under `/api` (`/api/metrics`) it would be exposed, so keep it at root `/metrics`.
- Caching: `/assets/` is immutable for 1 year (safe for Vite's hashed files; missing ones `=404`). The SPA fallback's internal redirect `try_files ... /index.html` also matches `location = /index.html`, so `no-cache` applies to every deep-link response. No server-level `add_header`, so no header-inheritance conflicts between locations.
- Proxy headers: `Host $http_host` keeps `:5173`; `X-Forwarded-For/Proto` are correct. Session cookies aren't port-scoped, so a cookie set on 8000 is also sent from the 5173 origin (same as the vite proxy). `http_version 1.1` is set and the `Connection` header defaults to `close`, so it works without keepalive (functionally harmless).
- `.dockerignore`: excluding `.env*`, `*.local`, `node_modules`, `dist`, `.git` keeps secrets and host dependencies out of the build context and image (the final image copies only `dist`, multi-stage). There's no `.env` in `frontend/`. Caveat: `VITE_*` values are baked into the bundle, so an allowed `.env` would expose them; since it's excluded, `API_BASE=''` (same origin), as intended.
- Latent: `USE_MOCKS` in `src/lib/config.ts` is `true` when `VITE_USE_MOCKS` is unset, but nothing in `src` references it (grep), so no effect. If a mock branch returns, the Dockerfile needs `ARG VITE_USE_MOCKS=false`.

Not reviewed: real build, start, and proxy round-trip (daemon down); existence of the `node:24.8.0-alpine` / `nginx-unprivileged:1.28.0-alpine` tags; the compose service (not written yet, out of scope). Suggested smoke after the daemon is back: `docker build frontend`, `docker run --rm --entrypoint nginx <img> -t` (reproduces #1 without api), `docker exec <c> id` (uid 101), and check `curl -i localhost:5173/metrics` returns `text/html`.
- Re-review: not needed (#1 recommended for `frontend-developer` when the compose service is written)

### CR-008 · 2026-11-14 · frontend-code-reviewer · T-023 (reviews T-021, KI-018 fix)
- Reviewed: `frontend/nginx.conf:8-12` (`resolver 127.0.0.11 valid=10s ipv6=off;` + `set $api_upstream http://api:8000;` + `proxy_pass $api_upstream$request_uri;`)
- Verdict: PASS_WITH_NOTES
- Verification: static review only. `nginx -t` / runtime not run (Docker daemon down); the developer's `npm run build` pass is cited as is.

Checked and fine:
- URI passing: a `proxy_pass` with a variable does no location-prefix substitution, so `$request_uri` (the original raw path+query, before decoding/normalization) passes through. The old `proxy_pass http://api:8000;` (no URI part) also passed the original URI, so keeping the `/api/...` prefix and preserving encoding behave the same (the backend is still mounted under `/api`).
- `Host $http_host`: no impact. The default `proxy_redirect` doesn't apply with a variable `proxy_pass`, but Host is the client's value, so backend redirects don't expose `api:8000` — there was nothing to rewrite before either.
- keepalive: `proxy_http_version 1.1` without `Connection ""` or an upstream block, so upstream connections closed per request before too. Nothing changed with the variable (small impact given 30–60s chats).
- resolver: 127.0.0.11 works only on user-defined compose networks, but the container always runs in compose, so acceptable. `ipv6=off` avoids needless AAAA lookups. `valid=10s` is a reasonable balance between following a recreated IP and DNS load (the default is the response TTL, which Docker keeps very short).
- Effect: nginx starts without `api` (resolution at request time) and follows a recreated `api`'s new IP within about 10s. KI-018 resolved.

| # | Severity | Location | Problem | Requested fix | Confidence | Handling |
|---|---|---|---|---|---|---|
| 1 | Minor | `frontend/nginx.conf:9` | With `api` missing or DNS failing, requests get 502 at request time (instead of a startup failure). Intended, but the problem doesn't surface until the first request | No action; compose `depends_on`/healthcheck can complement | plausible | open (accepted) |

Not reviewed: `nginx -t` syntax check, proxy recovery after a real `api` recreate, a round-trip with a query string. Suggested smoke after the daemon is back: `docker run --rm --entrypoint nginx <img> -t` (passes without api), `curl -i 'localhost:5173/api/<path>?q=a%20b'` to confirm the query is preserved, `docker compose up -d --force-recreate api` then 200 again within 10s.
- Re-review: not needed

### CR-009 · 2026-11-14 · backend-code-reviewer · T-022 (reviews T-020, non-root containers + compose split)
- Reviewed: `backend/app/WorkerImage.Dockerfile`, `service-docker-compose.yaml`, `system-docker-compose.yaml`, `frontend/Dockerfile`, `nginx.conf`, `.dockerignore`, `backend/app/.dockerignore`
- Verdict: PASS_WITH_NOTES
- Verification: static review only (Docker daemon down; no image build or start). The rendered config was not printed.

Checked and fine:
- alembic: `script_location=%(here)s/migrations`, cwd=/app. env.py only uses `fileConfig` (logging), no file writes. `post_write_hooks` (ruff) run only when generating a revision. Read-only for uid 10001 is enough.
- Runtime writes: logging is a StreamHandler (no files); no open/tempfile writes in app code. Only the fastembed cache `FASTEMBED_CACHE_PATH=/cache/fastembed` (chowned in the image; a new named volume keeps ownership via copy-up). fastembed uses this path for the HF cache too, and HOME exists (/home/app, `useradd --create-home`), so secondary caches are writable.
- `.venv` interpreter: a symlink to the uv image's system python (/usr/local), runnable by non-root (static judgment; confirm with a build).
- Env vars: POSTGRES_HOST/REDIS_HOST/QDRANT_URL/KAFKA_BOOTSTRAP_SERVERS (absent from .env, so the default localhost:9092), which would be localhost in the container, are all overridden via `environment` (compose `environment` beats `env_file`). kafka:29092 matches the INTERNAL listener. POSTGRES_PORT/REDIS_PORT in .env are the default ports, so fine.
- Cross-project `depends_on`: none (only frontend→api within the same project). If infra is down, alembic/worker fail and `restart: unless-stopped` retries. Acceptable.
- alembic && uvicorn: one replica, so no race. Scaling out would bring concurrent migrations (N/A now).
- ingest-worker exists only in the service file, removed from system. No duplication.
- `.dockerignore`: the build context is `./backend/app` and `backend/app/.dockerignore` excludes `.env`/`*.env`/`.venv`/`__pycache__`. The frontend also excludes `.env*`. Secrets are injected only at runtime via `env_file`.
- OAuth: GOOGLE_REDIRECT_URI=localhost:8000 with port 8000:8000 published + FRONTEND_URL=localhost:5173 (5173:8080), so the flow holds. CORS allow_origins is the same origin.
- `/metrics`: nginx proxies only `/api/`, so it isn't exposed on 5173. Reachable from the host via the 8000:8000 publish (intended, since Prometheus scrapes host.docker.internal:8000; same as before).

| # | Severity | Location | Problem | Fix | Confidence | Handling |
|---|---|---|---|---|---|---|
| 1 | Minor | `WorkerImage.Dockerfile:3-4` | The comment says bytecode is precompiled at build time, but `pyproject.toml` has no build-system, so the project isn't installed. `UV_COMPILE_BYTECODE` compiles only site-packages, not the /app sources (.py). At runtime /app is root-owned, so `__pycache__` can't be written (silently skipped). Only adds app-source compile cost (hundreds of ms to seconds) per start; no functional impact | Fix the comment, or add `RUN python -m compileall -q /app --exclude '\.venv'` after `COPY . .` | confirmed (from code) | open |
| 2 | Minor | `service-docker-compose.yaml` api | No api healthcheck. frontend `depends_on: api` guarantees start order only (small impact since nginx resolves DNS at runtime) | Optional: add a `/health` healthcheck | plausible | accepted |
| 3 | Minor | `WorkerImage.Dockerfile:20` | Numeric uid in `USER 10001` is correct. But if `/cache/fastembed` weren't created in the image, a bind mount would be root-owned, so keep the named volume (OK today) | No action | confirmed | accepted |

Not reviewed: image build, real uid 10001 start/migration, nginx -t, model download writes. Suggested smoke after the daemon is back: `docker compose -f service-docker-compose.yaml up -d --build`, then `docker exec api id`, `docker logs api` (alembic passes), `curl localhost:8000/health`, `curl -o /dev/null -w '%{http_code}' localhost:5173/metrics` (SPA index 200 or 404, not metrics).
- Re-review: not needed

### CR-010 · 2026-11-14 · backend-code-reviewer · T-024 (T-020 revision: project name + compileall)
- Reviewed: `system-docker-compose.yaml:4`, `service-docker-compose.yaml:56`, `monitoring-docker-compose.yaml:125`, `backend/app/WorkerImage.Dockerfile` (compileall added)
- Verdict: PASS_WITH_NOTES
- Verification: static review and grep only (Docker daemon down; no image build). The rendered config was not printed.

Checked and fine:
- Network name: system `name: rag_chatbot_system` → default network `rag_chatbot_system_default`. The external names at service:56 and monitoring:125 and the header comments all match.
- compileall ownership/permissions: runs as root before `USER 10001`; default umask 022 makes the pyc files root-owned 644, readable by non-root. No runtime writes needed.
- Interpreter: `ENV PATH` is set after this RUN, so `python` is the system python3.13 (uv image), and the venv uses the same interpreter, so the pyc magic number matches. Source mtimes are recorded in the pyc and COPY preserves mtimes, so no invalidation.
- `.venv` recompile: pyc files already built by `UV_COMPILE_BYTECODE` have current mtimes, so compileall skips them. Negligible time/size impact.

| # | Severity | Location | Problem | Fix | Confidence | Handling |
|---|---|---|---|---|---|---|
| 1 | Minor | `WorkerImage.Dockerfile:14` | compileall also walks the `.venv` site-packages. Some packages may ship deliberate syntax-error files (test data etc.); then the exit code is 1 even with `-q` and the build can break. uv's own compile ignores per-file failures | `python -m compileall -q -x '/\.venv/' /app` (app code only, also removes the duplicate walk) | plausible (build not confirmed) | open; apply if the build fails |

Not reviewed: real image build (#1 needs confirming), whether `__pycache__` is used after start. Re-review: not needed.

### CR-016 re-review addendum (T-043 revision)

Verdict: PASS_WITH_NOTES. Traced by code read only; build/lint by PM (OK), no browser pass.
- F1 fixed: `ChatPage.tsx:93-101` focuses the close button and adds a document Escape listener (cleanup on close); `closeList` (`:104`) restores focus to the Chats button, used by Escape, ✕, select (`:236`), New chat (`startNewChat`) and delete-active (`onActiveDeleted={onNewChat}`, `ChatListPanel.tsx:47`); `role=dialog`/`aria-modal`/`aria-label` only while open (`:216-218`); main column `inert={listOpen}` (`:240`). `closeList` reads only refs and a setter, so the effect's closure is not stale.
- F2 fixed: `useChat.ts:44-51` reads the active id from a ref at success time; deleting A then opening B no longer resets B.
- F3 fixed: explicit return types at `useChat.ts:31,39`.
- Known edge (open overlay below lg, widen past lg): confirmed by trace. Main stays `inert` and the aside keeps `role=dialog`, so the composer is unreachable until Escape, selecting a chat, or New chat. Not blocking: lg+ viewport change mid-overlay is rare, three exits exist, nothing is lost. Minor (tablet rotation is the realistic trigger). Cheapest fix if wanted: an effect that listens to `matchMedia('(min-width: 1024px)')` `change` and calls `closeList()`, or `inert={listOpen && !isLg}`.

## CR-017 — T-042 chat list + delete (uncommitted backend diff, feat/chat-session)

Verdict: PASS_WITH_NOTES. Read by code only; no live Postgres (docker down), so the SQL was not run through EXPLAIN. pytest/ruff by PM (151 passed), not re-run.

| # | Sev | Where | Finding | Fix | Conf. |
|---|-----|-------|---------|-----|-------|
| F1 | minor | `agent_orchestrator.py:~196-218` vs `send_message` | Ownership is checked before the lock, never re-checked after it. A send that passed `_get_owned_chat` just before a delete finished acquires the freed lock, runs the whole LLM turn, then the persist step hits the FK on the deleted chat (500) and recreates an orphan checkpoint thread. Window is one Redis round trip, and the user is deleting a chat they are chatting in. A second delete of a gone chat returns 204 instead of 404 (idempotent, fine). | Re-fetch the chat after the lock in both paths (cheap), or catch the FK error in persist and clear the thread | plausible |
| F2 | minor | `agent_orchestrator.py:~215` | `delete_chat` keeps the read transaction from `_get_owned_chat` open (no `db.commit()` as `send_message` does) while awaiting Redis and `adelete_thread`. Short I/O, so only a brief idle-in-transaction connection; the repo `commit()` ends it. | Optional `await db.commit()` after the ownership check, for consistency | confirmed |
| F3 | minor | `chat_repository.py:~152` | Title subquery is a select-list scalar subquery. With `LIMIT 100` and a sort on another expression Postgres usually postpones it, but it can run once per owned chat. Index `ix_chat_messages_chat_id_created_at` serves the ordered scan (role filtered on heap, `id` tiebreak needs an incremental sort over the few rows per chat). Fine at current scale; check EXPLAIN once a DB is up. | None now | plausible |

Verified OK:
- SQL: `max()` with no GROUP BY in a LATERAL always yields one row, so `JOIN LATERAL ... ON true` keeps chats without messages (NULL last_message_at; `coalesce(..., created_at)` handles it). Owner filter and `id` tiebreak are deterministic. `regexp_replace(..., 'g')`, `btrim`, `left(text, 61)` are valid Postgres. Max-61 chars is cut in SQL and the ellipsis is added in `_truncate_title`, so the boundary is exact (60 fits, 61 gets the ellipsis). One statement, no N+1. `ChatMessageRole.USER.value` matches the stored string role.
- Delete: ownership then lock (409 before any destructive step), checkpoint thread first, row second; a failure between them leaves the row, so the same request retries cleanly. Lock released in `finally` on every path after acquire; a cancellation hits the same `finally` as `send_message` (the one `await redis.delete` runs once). CASCADE on `chat_messages.chat_id` confirmed in `models/chat.py:48`. `adelete_thread` exists in langgraph-checkpoint-postgres >= 3.2.1.
- `send_message` refactor: same order (owner check, commit, acquire, try/finally release), same 409 message and `code_path` (`agent_chat_orchestrator-send_message-error`); only the warning log gained `action`. Unchanged.
- Layering, Korean docstrings, logs only in the service layer, no f-string logs: OK. `chat_model` etc. map by name through `from_attributes` on the dataclass, OK. The import order in the orchestrator constants block is off (`CHAT_LIST_LIMIT` after `CHAT_SUMMARY_MODEL`); ruff passed, so a nit only.
- Orphan `chat_usage_logs` / `agent_tool_call_logs` rows: acceptable for now. They are aggregate/audit data, carry only a chat id string, and the API docstring says so. Revisit if a privacy/erasure requirement shows up (they hold no message text).

Test gaps: repository tests assert on compiled statements and mocks, so they do not prove the SQL runs on Postgres (types, `lateral`, `left` binding). Add one integration check against a real Postgres when docker is up (chat with messages, without messages, 2 user messages, long and multi-space title, ordering). No test for the delete-vs-send race (F1) or for cancellation during delete. The delete tests use `InMemorySaver`, not `AsyncPostgresSaver`.
Not reviewed: frontend, Alembic (no migration in the diff), real checkpoint tables.

### CR-017 re-review addendum (T-042 revision)

Verdict: PASS. Code read only; pytest 154 / ruff by PM, not re-run by me.
- F1 closed: both `delete_chat` (`agent_orchestrator.py:221`) and `send_message` (`:255`) re-run `_get_owned_chat` after the lock, so a send that wins the lock after a delete finished gets 404 before `_run_turn`; the stale-`chat` risk is gone because `_run_turn` (`:257`) receives the re-fetched object. Delete-vs-delete returns 404 on the loser. The lock is held by one request through delete, so no check-then-act gap remains.
- F2 closed: `db.commit()` at `:216` (delete) ends the read transaction before Redis and `adelete_thread`; a second commit at `:222` / `:256` does the same after the re-check, and the re-check's own 404 raises before it.
- Lock: every post-acquire path (re-check 404/403, adelete_thread or delete error, `_run_turn` error, cancellation) is inside `try/finally` and releases once; a 409 raises in `_acquire_turn_lock` before `try`, so a lock held by someone else is never deleted. `send_message` keeps the 409, rollback and persist behavior (`_run_turn` unchanged).
- Tests: the two `after_lock` tests assert 404, no agent / no thread or row delete, lock released; the ordering test proves commit precedes lock and `adelete_thread`. Minor gap: no assertion that `_run_turn` gets the second `chat` (both stubs return equal objects), not blocking.

## CR-018 — T-047 SSE chat streaming (uncommitted frontend diff, feat/chat-stream)

Verdict: PASS_WITH_NOTES. No blocking findings. `npm run build` OK (109 modules, JS 323 kB / 98.7 kB gzip), `npm run lint` clean (both re-run by me). No browser or screen-reader pass; everything below is traced from code, except the parser, which I ran.

| # | Sev | Where | Finding | Fix | Conf. |
|---|-----|-------|---------|-----|-------|
| F1 | minor | `useChat.ts:140-153` vs cache write `:205-217`; `ChatPage.tsx:73-82,192` | On `done` the optimistic bubbles (`turn.id`, `${turn.id}-answer`) are replaced by cache messages with `chatMessageId(...)` ids. Keys change, so both bubbles unmount/remount (text selection lost, possible flicker), and `lastMessageId` changes, so the log scrolls smoothly to the START of the answer (`block: 'start'`). A user who was reading the end of a long streamed answer is jumped back up at the moment it completes. Streaming itself never follows the tail (id is stable during the stream). | Give the optimistic user/answer messages the same ids the cache write will use (`chatMessageId(id, n)` / `n+1`, n = history length), so keys survive; the scroll effect then does not fire on done. | confirmed by trace |
| F2 | minor | `useChat.ts:198-204`, `MessageBubble` | Each delta calls `setTurn`, which re-renders `ChatPage` and rebuilds `messages`; every `MessageBubble` (not memoized, citations included) re-renders per token. Cost is plain text, so cheap for ~50 messages. It grows with chat length and token rate. | `export const MessageBubble = memo(...)` (history messages are stable refs from the cache, so it works), or coalesce deltas per animation frame. Measure first; not urgent. | plausible |
| F3 | minor | `ChatPage.tsx:311-316` | `aria-busy` on a `role=log` is honored inconsistently: several screen reader/browser pairs ignore it and announce every text growth (token chatter). Where honored, it works: the question and the pre-token ThinkingIndicator are announced normally, busy is set from the first token and cleared on done, and the finished answer is a remounted node (F1), so it is announced once. | Keep. For robustness, put `aria-live="off"` / `aria-hidden` on the in-flight bubble and announce the final answer via the existing log, or test with VoiceOver and NVDA once. | plausible |
| F4 | minor | `frontend/nginx.conf:19` | `proxy_buffering off` is location-wide. It does not affect uploads (request side is `proxy_request_buffering`, untouched, and `client_max_body_size` is separate). It does change every `/api/` response from buffered to pass-through, so a slow client holds an upstream connection for the whole body. Negligible for the small JSON responses here. The backend already sends `X-Accel-Buffering: no` (D-018a), which turns buffering off per response, so the global directive adds nothing. | Drop the directive and rely on the header (smaller blast radius), or keep it as defense in depth knowingly. | confirmed |
| F5 | nit | `chat.ts:88,90` | Stream `error` and truncated-stream failures are `ApiError(200, ...)`. `turnErrorText` maps status 200 to the generic "Couldn't get an answer" copy, which is right (no raw `detail`, KI-058), but a 200-status error is misleading if anyone later branches on `status`. A malformed frame throws `SyntaxError`, which takes the same generic path. | Optional: use status 0 or a dedicated `StreamError`. | confirmed |

Verified OK:
- Parser (`sse.ts`), run by me with a scratch script outside the repo against the real file: a stream with CRLF, multi-byte Korean text and multi-line `data:` was split at EVERY byte offset (including inside `\r\n`, inside `\r\n\r\n`, inside a UTF-8 sequence): 0 mismatches against the unsplit result. Multi-line data joins with `\n`. A trailing frame with no blank line is dropped (spec behavior; `streamMessage` then throws the "ended before complete" error, matching D-018). `: ping` comment frames and unknown events are skipped. Empty `data:` yields `''` and `JSON.parse` fails into the generic error path.
- Abort and cleanup: `controller.abort()` rejects the pending `reader.read()`, the generator's `finally` cancels the reader, and `run`'s catch returns on `signal.aborted` (no error flash). Early `return` on `done`/`error` runs the same `finally`, closing the connection. The backend persists BEFORE emitting `done` (D-018b), so cancelling right after `done` cannot lose the turn. After an abort, the loop could process at most frames already buffered, and `onToken` is guarded by `t?.id === next.id`, so a late delta cannot land on another turn (retry only runs after the previous stream ended).
- Unmount or navigating away mid-stream: the turn keeps running by existing design (unchanged from the non-streaming version). Tokens then call `setTurn` on an unmounted hook, which is a harmless no-op in React 19, and `done` writes only into a still-cached chat. Switching chats shows no foreign tokens (`visibleTurn` filters by chatId). Sending in another chat aborts the first stream via `abortInflight`; as before, only the answer is lost, and it is all-or-nothing.
- Streaming text vs cache write on `done`: the answer from `done` is authoritative (`toAnswer(done)`), and the streamed text is discarded, not merged. The cache write and `setTurn(null)` run in the same tick, so no duplicate and no missing bubble was found by trace (the query result updates synchronously; only observer notification is batched). Error after partial tokens: `answer` is cleared and the question is kept for Retry; `retry` spreads a turn with `answer: ''`.
- Types: `StreamTokenEvent`, `StreamErrorEvent`, and `ChatMessageResponse` match D-018. `JSON.parse(...) as` casts sit at the trust boundary (backend-owned contract), acceptable; no `any`, no default export, no raw `fetch` in components (`apiResponse` in `lib/api`). `apiFetch` behavior is unchanged by the refactor. Pre-stream non-2xx stays JSON `ApiError`, so 401/409/403/404 handling is intact.
- Not blocking and not in scope: no automated parser test exists (no runner in `frontend/`); the check above lives only in my scratch dir. Worth adding once a runner (vitest) is approved.

Not reviewed: live backend stream and nginx behavior (docker not run), screen readers, long-chat render profiling.

### CR-018 re-review (T-048): F1 and F4 fixes from T-047

Verdict: PASS. No blocking findings. `npm run build` OK (JS 323.50 kB / 98.71 kB gzip) and `npm run lint` clean, both re-run by me. Traced from code only; no browser pass.

- F1 resolved (`useChat.ts:139-160`). The in-flight question and answer get `chatMessageId(chatId, n)` and `n+1`, with n = history length. These are the ids the cache write on done produces (`:217,:224`), so the keys survive and `lastMessageId` is unchanged on done.
  - No duplicate keys: the in-flight ids are always at or above the history length, and the cache write appends at the same n. `staleTime: Infinity` means no refetch lands mid-turn. `abortInflight` only invalidates with `refetchType: 'none'`.
  - Failed turn plus Retry: the question stays at `msgId(0)` (the answer bubble is dropped when `answer` resets to ''). Retry spreads the same turn, so the id is stable and no answer bubble shows until the first token.
  - Brand-new chat: ids are `${turn.id}-0` until createChat returns. They then switch to `chatMessageId(id, 0)` once, because the cache is seeded with `messages: []`. This is before any token arrives, so the only effect is one remount of the user bubble. Accepted, cosmetic.
  - Residual, minor and not new: if a refetch landed between the server persisting and `done`, the cache write would append to the already-refetched history. This needs a forced refetch, which `staleTime: Infinity` rules out. No action.
- F4 resolved (`nginx.conf:17`). `proxy_buffering off` is gone and a comment now points to the backend `X-Accel-Buffering: no` header (D-018a). The live stream through nginx was not run (docker not run), so one manual check remains: tokens should arrive incrementally via the frontend container.

## CR-019 — T-046 SSE chat streaming backend (uncommitted `git diff -- backend`, feat/chat-stream)

Verdict: CHANGES_REQUIRED (1 blocking). PM's run was not repeated (pytest 175 passed, ruff clean). I ran two scratch repros outside the repo against the real Starlette 1.3.0 / anyio 4.13.0 / uvicorn 0.49.0 in `backend/app/.venv`.

| # | Sev | Where | Finding | Fix | Conf. |
|---|-----|-------|---------|-----|-------|
| F1 | major (blocking) | `agent_orchestrator.py:_stream_turn` finally (`redis.delete`), `_abort_stream`/`_shielded`; `chats.py:_sse_frames` | **The cleanup never runs when the client disconnects while the agent is working (the common case).** uvicorn advertises `spec_version` "2.3" (`h11_impl.py:206`, `httptools_impl.py:227`), so `StreamingResponse.__call__` takes the `create_collapsing_task_group` (anyio) branch and cancels `stream_response` via a cancel scope on `http.disconnect`. anyio cancellation is level-triggered: every later suspending `await` in that task raises `CancelledError` again. The `except BaseException` path calls `_shielded(...)`, whose `except CancelledError: await task` gets re-cancelled, and awaiting a task directly cancels it, so the rollback task is killed. Then `await self._redis.delete(lock_key)` in the finally is cancelled too. Repro with the real `StreamingResponse` (spec 2.3) and the repo's `_shielded`: disconnect after the first chunk leaves the log empty (neither rollback nor lock delete completed). Effects in prod: (a) lock stays until TTL 300s, so a retry or resend in the same chat gets 409 for up to 5 min (the frontend aborts the stream on chat switch/new send, `useChat.ts:161`); (b) the thread is not restored, which is the CR-012 F1 case (dangling tool_calls make the next turn fail at the provider) once the lock expires; (c) the graph stream close in `_abort_stream` is also skipped. Plain-asyncio cancel (what the tests and `ainvoke` path use) is edge-triggered and works, which is why it was missed. | Run all cleanup under an anyio shield: `with anyio.CancelScope(shield=True): await stream.aclose(); await self._rollback_thread(...)` in `_abort_stream`, and the same around `redis.delete` in `_stream_turn`'s finally. anyio is already installed (Starlette dep). Verified: the same repro with `CancelScope(shield=True)` around the rollback and the delete gives `['rollback done', 'lock deleted']`. Keep `_shielded` or drop it in favor of the scope; it is not sufficient alone. | confirmed (repro) |
| F2 | minor (test gap, blocking with F1) | `tests/api/v1/endpoints/test_chats.py:443` `test_stream_message_failed_with_client_disconnect` | The test does go through the real app/middleware and the anyio task-group path (no `spec_version` in scope defaults to "2.0"), but the fake stream's `finally` only does `closed.set()` (sync). Nothing awaits in cleanup, so F1 cannot show. The orchestrator tests (`test_agent_orchestrator.py:1565,1618`) cancel with plain `task.cancel()`/`aclose()`, again edge-triggered. | Make the fake stream's finally `await asyncio.sleep(0)` before `closed.set()`, or drive the real `_stream_turn` with a fake redis/graph whose delete/rollback await, under `StreamingResponse` with `spec_version` "2.3". Assert rollback ran and `redis.delete` was called. | confirmed |
| F3 | minor | `_stream_turn` / `_sse_frames` | If the disconnect lands while the generator is suspended at a `yield` (Starlette is in `await send`), Starlette does not `aclose()` the body iterator; cleanup waits for the asyncgen GC finalizer (runs in a separate task, so it is outside the cancel scope and works, but timing is non-deterministic). Not a bug on its own. | Optional: nothing, or `StreamingResponse(..., background=...)` is not helpful; accept. | plausible |
| F4 | minor | `_abort_turn` `logger.exception` | Every client disconnect (Cancelled/GeneratorExit) is logged at ERROR with a traceback as "메시지 처리 실패". Pre-existing pattern for non-stream cancel, but disconnects are now routine. | Log `CancelledError/GeneratorExit` at `info`/`warning` without traceback. | confirmed |

Judgment on the developer's deviations:
1. Per-await deadline: OK. `deadline` is absolute (`loop.time() + 240`), so time spent suspended at a `yield` (slow client) counts against the next await. Graph activity ends by 240s. Remaining unbounded parts are `_finish_turn` (DB, prune) and cleanup, the same as the non-stream path; they must fit in the 60s slack to the 300s TTL. The lock cannot expire under a running graph.
2. Close graph stream, then rollback: the order is right (aclose before `aupdate_state`). It does not take effect on the disconnect path until F1 is fixed.
3. Usage-log failure after `add_turn_messages`: not made worse. `_finish_turn` has the same sequence as the old `_run_turn`; the stream only adds an `error` event after the tokens were shown, and a client retry duplicates the saved turn exactly as in non-stream KI-044. Keep KI-044 OPEN.

Verified OK:
- Non-stream behavior unchanged: `send_message` still `_run_turn` under `asyncio.timeout(240)`, same log/rollback, endpoint returns `_to_message_response` (same fields). `stream_usage=True` only affects streaming calls, so the loadtest mock (rejects stream=true) is not hit by the non-stream path.
- Pre-stream errors: `_lock_owned_chat` runs before the `StreamingResponse` is created, so 401/403/404/409/422 are JSON; the lock is deleted on any failure there (`except BaseException`).
- DB session: FastAPI 0.136.3 keeps the yield dependency open until the response ends. `_lock_owned_chat` commits before the LLM loop, so no connection is held while streaming; the session is used only in `_finish_turn`.
- Exactly one of done/error: done is in `else` (after persistence), errors in except branches; AppException message vs generic message is correct; `BaseException` re-raises without yielding.
- Layering and conventions: logs only in the service layer; endpoint has no logging; Korean docstrings/comments; `GENERIC_ERROR_MESSAGE` shared with the handler; `_answer_token` limits to `langgraph_node == "model"`.
- Accepted per D-018c: lock left until TTL if the client drops before the generator's first iteration.

Not reviewed: live Redis/Postgres/Qdrant/OpenAI stream, nginx pass-through, load behavior (many concurrent streams x 240s). Coverage gaps: F2, plus no test for the deadline firing mid-stream with a real clock (fake only), and none for disconnect during `_finish_turn`.

### CR-019 re-review (T-046 / T-045 revision, uncommitted, feat/chat-stream)

Verdict: PASS_WITH_NOTES. F1 and F2 are resolved. F4 is done. No blocking items.

Checks run (dummy env, from `backend/app`):
- My CR-019 repro `starlette_fix.py` (real `StreamingResponse`, spec_version 2.3, and the repo's `_shielded`) now prints `['rollback done', 'lock deleted']`. Before the fix the log was empty.
- `PYTHONPATH=. uv run pytest -q`: 176 passed. (Plain `uv run pytest` fails collection with ModuleNotFoundError in my shell; I did not look into why. `PYTHONPATH=.` works.)
- Negative check: I temporarily replaced `with anyio.CancelScope(shield=True):` in `_shielded` with `if True:`. This gave 2 failed, 174 passed: `test_stream_message_failed_with_client_disconnect` and `test_stream_message_failed_with_anyio_cancel_scope_after_first_token`. So both new tests fail without the fix. The file was restored (`cp` back; the diff stat is unchanged).
- Scratch `hang2.py`:
  - Non-streaming asyncio `task.cancel()`: `_shielded` runs the inner task to completion, then raises CancelledError. This is the same behavior as before.
  - An outer `anyio.move_on_after` scope: the shielded call finishes, then the scope cancels (`cancel_called=True`). No hang.

Notes (non-blocking):
- N1, shutdown risk. The shield makes the cleanup uncancellable (Redis delete, `aclose`, rollback), so a hung Redis or DB call in the cleanup can delay shutdown or disconnect handling. This is bounded by the redis-py and DB socket timeouts. That is not worse than before, because the old code also awaited the task. Confirm the Redis client has `socket_timeout`; I did not check.
- N2, anyio dependency. `anyio` is locked at 4.13.0 (`uv.lock`) and is a hard dependency of starlette, fastapi, httpx and openai, so the import cannot go missing. It is absent from `pyproject.toml`. `uv add anyio` is not required to merge. It is a cheap one-liner that makes the direct import honest, so do it if you want, as a follow-up.
- N3, the F3 note stands. A disconnect while the generator is suspended at a `yield` relies on the asyncgen finalizer. This is accepted.

Not reviewed: live Redis/Postgres/OpenAI streaming and nginx pass-through.
