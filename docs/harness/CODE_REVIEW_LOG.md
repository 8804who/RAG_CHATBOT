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
