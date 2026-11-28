# API Contracts

> Owners: contract design and change approval `system-architect` · backend implementation sync `backend-developer` · frontend type sync `frontend-developer`
> **The code is canonical.** Request/response field details: `backend/app/schemes/requests.py`, `schemes/responses.py`, and the running OpenAPI at `http://localhost:8000/docs`. Frontend types: `frontend/src/lib/api/*.ts`.
> This doc holds the endpoint list, auth, error rules, and the change procedure. Don't copy fields here.

## Common rules

- Base path: `/api/v1` (the frontend calls same-origin through the Vite proxy in dev or nginx in Docker; `apiFetch` uses `credentials: 'include'`).
- Format: JSON requests and responses.
- Auth: `session` cookie (issued in the Google OAuth callback). Protected endpoints check it via the `get_current_user` dependency; failure → 401.
- Error response shape: `{"detail": "<message safe to show the user>"}`. Undefined exceptions → 500.

## Endpoints

| Method | Path | Auth | Request | Response | Main errors |
|---|---|---|---|---|---|
| GET | `/auth/google/login` | – | – | Redirect to Google | |
| GET | `/auth/google/callback` | – | OAuth query | Sets the `session` cookie, then redirects | |
| POST | `/auth/google/logout` | cookie | – | 204 | |
| GET | `/auth/me` | ✔ | – | `UserResponse` | 401 |
| GET | `/models` | – | – | `AvailableModelsResponse` (embedding, chat) | |
| GET | `/collections` | ✔ | – | `CollectionsResponse` | 401 |
| GET | `/collections/{name}` | ✔ | – | `CollectionDetailResponse` | 404 |
| POST | `/collections` | ✔ | `CreateQdrantCollectionRequest` | 201 | 400 model/dimension mismatch, 409 duplicate |
| PATCH | `/collections/{name}` | ✔ | `UpdateQdrantCollectionRequest` | 200 | 404 |
| DELETE | `/collections/{name}` | ✔ | – | 204 | 404 |
| POST | `/collections/{name}/documents` | ✔ | `IngestDocumentRequest` (`filename`, `content` — JSON text, not multipart) | 202 `UploadAcceptedResponse` | 400 |
| GET | `/collections/{name}/documents` | ✔ | – | `DocumentsResponse` | 404 |
| GET | `/collections/{name}/documents/{document_id}/status` | ✔ | – | `DocumentStatusResponse` | 404 |
| GET | `/collections/{name}/documents/{document_id}/chunks` | ✔ | – | `DocumentChunksResponse` | 404 |
| DELETE | `/collections/{name}/documents/{document_id}` | ✔ | – | 204 | 404 |
| POST | `/chats` | ✔ | `CreateChatRequest` (`chat_model`, `collection_name?`) | 201 `ChatResponse` | 400 unsupported model, 400 collection missing |
| GET | `/chats` | ✔ | – | `ChatListResponse` (`chats[]`: `id`, `title` (first user message, whitespace-collapsed, > 60 chars → 60 + "…"; null if no messages), `chat_model`, `collection_name`, `created_at`, `last_message_at` (null if no messages)). Caller's chats only, ordered by `COALESCE(last_message_at, created_at)` DESC, `id`; max 100, no pagination. | 401 |
| DELETE | `/chats/{chat_id}` | ✔ | – | 204. Deletes the chat, its messages (cascade) and its agent checkpoint thread. Usage/tool-call logs are kept. | 403 someone else's chat, 404, 409 a turn of this chat is in progress (`ChatTurnInProgressError`) |
| POST | `/chats/{chat_id}/messages` | ✔ | `SendChatMessageRequest` (`query` 1–4000 chars) | `ChatMessageResponse` (`content`, `citations[]`) | 403 someone else's chat, 404, 409 another turn of this chat is in progress (`ChatTurnInProgressError`). A failed turn stores nothing (D-016), so the client can resend. |
| POST | `/chats/{chat_id}/messages/stream` | ✔ | `SendChatMessageRequest` | 200 `text/event-stream`: `token` / `done` (`ChatMessageResponse`) / `error` events, see SSE note below | Before the stream starts: 403, 404, 409, 422 as JSON `{"detail"}`. After the stream starts: in-band `error` event (turn rolled back, D-016). |
| GET | `/chats/{chat_id}/messages` | ✔ | – | `ChatHistoryResponse` (`chat_model`, `collection_name`, `messages[]`: `role`, `content`, `citations[]` (empty for user rows), `created_at`; oldest first) | 403 someone else's chat, 404 |
| GET | `/usage/stats` | ✔ | – | `UsageStatsResponse` | 401 |

SSE (`/chats/{chat_id}/messages/stream`, D-018): each frame is `event: <name>` + `data: <JSON>`. `token` `{"content"}` is an answer text delta. `done` is the authoritative final `ChatMessageResponse`, sent after persistence; the client replaces the streamed text with it. `error` `{"detail"}` means the turn stored nothing. A stream ends with exactly one `done` or `error`. Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Clients use `fetch` + `ReadableStream` (POST, so no `EventSource`).

Outside `/api`: health check `/health` and `/`, and Prometheus `/metrics` (root path, unauthenticated, not proxied by nginx; KI-020). These are excluded from the API call log and the uvicorn access log unless `LOG_INFRA_ENDPOINTS=true`.

## Error codes (`backend/app/exceptions/`)

| Exception | HTTP |
|---|---|
| `UnsupportedEmbeddingModelError`, `EmbeddingModelDimensionMismatchError` | 400 |
| `EmbeddingGenerationError` | 502 |
| `CollectionMetaNotFoundError`, `EmptyDocumentError`, `DenseVectorNotConfiguredError` | 400 |
| `DocumentNotFoundError` | 404 |
| `CollectionNotFoundError` | 404 |
| `CollectionAlreadyExistsError` | 409 |
| `ChatNotFoundError` | 404 |
| `ChatAccessDeniedError` | 403 |
| `ChatTurnInProgressError` | 409 |
| `UnsupportedChatModelError` | 400 |
| Any other unhandled exception | 500 |

## Access rules

- Chats: owner only (`ChatAccessDeniedError`, IDOR protection).
- Usage: the requester's own data only.
- Collections and documents: no owner concept today; every logged-in user can read, edit, and delete → [KNOWN_ISSUES.md](KNOWN_ISSUES.md) KI-006.

## Contract change procedure

1. Propose the change → `system-architect` approves → record it in [DECISION_LOG.md](DECISION_LOG.md).
2. Update this doc (one line in the change history).
3. Assign **both** a `backend-developer` task (schema, endpoint, tests) and a `frontend-developer` task (`src/lib/api` types, hooks). Never complete with only one side changed.
4. If backward compatibility breaks, `qa-engineer` runs regression tests.

## Change history

| Date | Change | Decision |
|---|---|---|
| 2026-11-14 | Harness adopted; contract documented from the current code | — |
| 2026-11-14 | Root `/metrics` added (T-015); not part of `/api` | D-012 follow-up |
| 2026-11-28 | `POST /chats/{chat_id}/messages/stream` (SSE) added; non-streaming endpoint unchanged (T-044) | D-018 |
