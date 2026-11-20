# Kafka 기반 비동기 인제스트 파이프라인 (구현 설명서)

> 이 문서는 **실제 구현된** Kafka 인제스트 파이프라인이 *어떻게 짜여 있고, 왜 그렇게
> 짰는지*를 코드 경로와 함께 설명합니다. 설계 배경/대안 비교는
> [RAG_ARCHITECTURE.md](./RAG_ARCHITECTURE.md) §1–5, 임베딩/컬렉션 기본기는
> [EMBEDDING_AND_COLLECTIONS.md](./EMBEDDING_AND_COLLECTIONS.md)를 참고하세요.
>
> 한 줄 요약: **문서 인제스트(쓰기 경로)를 HTTP 요청에서 떼어내 Kafka 뒤로 옮겼습니다.**
> 업로드는 즉시 `202`로 응답하고, 파싱·임베딩·적재는 별도 워커 프로세스가 뒤에서 처리합니다.

---

## 0. 왜 Kafka인가 (무엇이 바뀌었나)

기존 인제스트는 **업로드 HTTP 요청 안에서 동기로** 청킹 → 임베딩 → Qdrant 적재까지
끝냈습니다(`DocumentService.ingest`). 큰 문서면 응답이 막히고, 700번째 청크에서 실패하면
처음부터 다시 해야 하며, API 서버 수가 곧 임베딩 처리량이 되는 문제가 있었습니다.

이번 변경으로:

| 문제 | 해결 |
|---|---|
| 응답 지연 | 업로드는 메시지 produce 후 **즉시 `202 Accepted`** 반환 |
| 부분 실패 | 단계별 토픽 → 해당 단계만 재시도/재생, 실패는 `documents.dlq`로 격리 |
| 스케일 | Embed/Index 워커를 **API와 독립적으로 수평 확장**(컨슈머 그룹 파티션) |
| rate limit | 컨슈머가 자기 페이스로 pull → 자연스러운 backpressure |
| 진행 가시성 | 단계별 상태를 Postgres `documents` 테이블에 기록 → 프론트가 폴링 |

읽기(질의) 경로는 사용자가 응답을 기다리는 동기 경로라 **Kafka를 쓰지 않습니다**(설계 그대로).

---

## 1. 전체 흐름

```
POST /collections/{c}/documents  ──(202 Accepted)──►  즉시 반환
        │
        │ DocumentService.accept_upload: 상태 UPLOADED 기록 + produce
        ▼
  [documents.uploaded] ──► Parser Worker ──► [documents.parsed] ──► Embed Worker
                             (청킹)          (청크당 1메시지)        (임베딩)
                                                                        │
                                                                        ▼
                                                                 [chunks.embed]
                                                                        │
                                                                        ▼
                                                                  Index Worker
                                                                  (Qdrant upsert)
                                                                        │
                                             모든 청크 적재 완료 시 ──► 상태 INDEXED
                                                                        │
  어느 단계든 재시도 소진 시 ──► [documents.dlq] + 상태 FAILED  ◄──────────┘

  진행 상태: Postgres `documents` 테이블(UPLOADED→PARSING→EMBEDDING→INDEXED→FAILED)
  프론트: GET /collections/{c}/documents/{id}/status 폴링
```

핵심 분리 원칙: **쓰기 경로는 Kafka 뒤로, 각 단계 경계 = 토픽 하나.**

> **참고 — Parser Worker의 현재 역할**: 프론트가 이미 추출된 텍스트를 보내므로
> 현재 파서는 파일 파싱 없이 **청킹만** 합니다. 실제 파일 파싱(PDF/HWP 등)이 들어올
> 자리입니다.

---

## 2. 토픽 설계

토픽 이름 상수는 [`schemes/events/topics.py`](../backend/app/schemes/events/topics.py)에 있습니다.

| 토픽 | producer | consumer | payload(요지) |
|---|---|---|---|
| `documents.uploaded` | 업로드 endpoint | Parser Worker | `document_id, collection_name, filename, content, requester_*` |
| `documents.parsed` | Parser Worker | Embed Worker | 청크당 1메시지 + `embedding_model, dense/sparse_vector_name, total_chunks` |
| `chunks.embed` | Embed Worker | Index Worker | 임베딩 결과 `dense, sparse_indices/values` + payload용 메타 |
| `documents.dlq` | 모든 워커 | 운영/재처리 | `stage, error, retry_count, source_topic, original(원본 메시지)` |

설계 규칙:

- **파티션 키 = `document_id`** → 한 문서의 청크들이 같은 파티션으로 가서 문서 단위
  국소성/순서가 보장됩니다. (모든 `publish(topic, key=document_id, value=...)`)
- **단계별 토픽 분리** → 단계마다 컨슈머 그룹·스케일·재시도 정책을 독립적으로 가져갑니다.
- 토픽은 API·워커 시작 시 [`ensure_topics`](../backend/app/clients/kafka_client.py)로
  멱등 생성합니다(dev 브로커는 자동 생성도 켜져 있음).

---

## 3. 메시지 스키마 (이벤트)

토픽 페이로드는 Pydantic 이벤트로 **코드에 계약을 강제**합니다 —
[`schemes/events/ingestion.py`](../backend/app/schemes/events/ingestion.py).

```python
class _KafkaEvent(BaseModel):
    def to_bytes(self) -> bytes:           # 발행 시: JSON bytes로 직렬화
        return self.model_dump_json().encode()

    @classmethod
    def from_bytes(cls, raw: bytes):        # 소비 시: JSON bytes → 이벤트
        return cls.model_validate_json(raw)
```

- `DocumentUploadedEvent` — 업로드 원문(`content` 포함)
- `DocumentParsedEvent` — 청크 1개 + 컬렉션 고정 임베딩 모델/벡터 이름/`total_chunks`
- `ChunkEmbeddedEvent` — 임베딩 결과(dense + sparse) + 적재용 payload 메타
- `DlqEvent` — 실패 격리(단계·에러·재시도 횟수 + 원본 메시지)

sparse 벡터는 JSON 직렬화를 위해 `SparseVector`(indices/values)를
`sparse_indices` / `sparse_values` 리스트로 풀어서 싣고, Index 단계에서 다시 조립합니다.

---

## 4. 레이어별 구현 (기존 규칙 그대로)

컨벤션은 그대로 유지했습니다: `endpoint → service → repository → client`,
싱글톤 `@lru_cache get_*` 팩토리, 주석/독스트링 한국어, import 루트 `backend/app`.

### 4.1 Client 레이어 — Kafka 래핑

[`clients/kafka_client.py`](../backend/app/clients/kafka_client.py)

- `KafkaProducerClient` — `AIOKafkaProducer`를 감싸 생명주기(`start`/`publish`/`close`)를
  캡슐화. `enable_idempotence=True`(중복 produce 방지), `acks="all"`(내구성).
- `ensure_topics(topics)` — `AIOKafkaAdminClient`로 토픽을 멱등 생성.
- [`dependencies/clients.py`](../backend/app/dependencies/clients.py)의
  `get_kafka_producer()`로 **싱글톤** 노출(프로세스당 커넥션 1개).

> **왜 producer만 FastAPI에 두나**: API는 메시지를 *발행만* 합니다. *소비*는 워커의 몫이라
> 컨슈머는 `workers/`에서 자체 루프로 돕니다.

### 4.2 Service 레이어 — 발행 + 단계별 처리

한 서비스는 얇게 유지하고 DI로 조립해, **API와 워커가 같은 `get_*` 팩토리를 공유**합니다.

- [`services/ingestion/document_service.py`](../backend/app/services/ingestion/document_service.py)
  `DocumentService.accept_upload` — 상태 레코드를 `UPLOADED`로 생성하고
  `documents.uploaded`에 원문을 발행한 뒤 **임베딩을 기다리지 않고** 반환. (조회/삭제는 유지)
- [`parser_service.py`](../backend/app/services/ingestion/parser_service.py)
  `ParserService.handle` — 컬렉션 메타에서 임베딩 모델을, Qdrant에서 dense/sparse 벡터
  이름을 확보 → `chunk_text`(재사용) → `total_chunks` 기록 + 상태 `PARSING` → 청크마다
  `documents.parsed` 발행.
- [`embed_ingest_service.py`](../backend/app/services/ingestion/embed_ingest_service.py)
  `EmbedIngestService.handle` — `EmbeddingService.embed_documents`(재사용)로 임베딩 →
  첫 청크에서 상태 `EMBEDDING` → `chunks.embed` 발행.
- [`index_service.py`](../backend/app/services/ingestion/index_service.py)
  `IndexService.handle` — `IngestPoint` 구성 → `upsert_points`(멱등) → 진행도 원자적 증가 →
  마지막 청크에서 상태 `INDEXED` + 성공 이력(`DocumentManageLog`) 기록.

### 4.3 Repository / Model — 진행 상태 추적

- [`models/document.py`](../backend/app/models/document.py) — `documents` 테이블
  (`DocumentRecord`) + `DocumentStatus` enum. `Base.metadata.create_all`이 시작 시 생성.
- [`repositories/document_status_repository.py`](../backend/app/repositories/document_status_repository.py)
  — `create/get/set_status/set_total_chunks/increment_indexed/set_failed/delete`.

**동시성 포인트 — `increment_indexed`**: 여러 Index 워커가 같은 문서의 서로 다른 청크를
병렬 적재하므로, 적재 완료 수는 **SQL 표현식 + RETURNING**으로 원자적으로 증가시킵니다.

```python
update(DocumentRecord)
    .where(DocumentRecord.document_id == document_id)
    .values(indexed_chunks=DocumentRecord.indexed_chunks + 1)
    .returning(DocumentRecord.indexed_chunks, DocumentRecord.total_chunks)
```

증가 후 값을 원자적으로 돌려받아, `indexed_chunks == total_chunks`를 **정확히 한 워커만**
관측 → 그 워커만 상태를 `INDEXED`로 바꿉니다(레이스 없음).

### 4.4 Worker 레이어 — 별도 프로세스 컨슈머

[`workers/`](../backend/app/workers/) — API(`uvicorn main:app`)와 코드·DI는 공유하지만
**다른 프로세스로 배포**되어 독립 스케일됩니다.

- [`runner.py`](../backend/app/workers/runner.py) — 세 워커 공통 소비 루프.
- `parser_worker.py` / `embed_worker.py` / `index_worker.py` — 각자 토픽·컨슈머 그룹·처리
  서비스를 `run_worker(...)`에 넘기는 얇은 엔트리포인트.

```python
# workers/embed_worker.py (요지)
service = get_embed_ingest_service()          # API와 동일한 DI 팩토리 재사용
await run_worker(
    topic=TOPIC_DOCUMENTS_PARSED,
    group_id="embed-workers",                 # 그룹으로 파티션 분배 → 프로세스 늘리면 확장
    stage="embedding",
    event_type=DocumentParsedEvent,
    handler=service.handle,
)
```

워커는 요청 스코프 밖이라 메시지마다 `AsyncSessionLocal()`로 **자체 DB 세션**을 엽니다.

---

## 5. 신뢰성 — at-least-once, 재시도, DLQ

[`runner.py`](../backend/app/workers/runner.py)의 소비 루프가 신뢰성 정책을 담습니다.

- **수동 커밋 + at-least-once**: `enable_auto_commit=False`. 메시지를 처리한 뒤에만 offset을
  커밋 → 크래시 시 재처리(중복 가능). 그래서 Qdrant `upsert_points`는 **같은 `chunk_id`로
  덮어쓰는 멱등** 연산이어야 하고, 실제로 그렇습니다(재처리해도 중복 포인트가 안 쌓임).
- **내부 재시도(지수 백오프)**: 처리 실패 시 `INGEST_MAX_RETRIES`회까지 재시도.
- **DLQ 격리**: 재시도 소진 또는 역직렬화 불가(포이즌) 메시지는 문서를 `FAILED`로 표시하고
  `documents.dlq`로 보낸 뒤 **offset을 전진**시킵니다 → 포이즌 메시지가 파티션을 영원히
  막지 않습니다.

```
성공        → handler 처리 → commit
처리 실패    → N회 재시도 → 소진 시 set_failed + DLQ → commit
역직렬화 실패 → 재시도 없이 바로 DLQ → commit
```

---

## 6. API 계약 변화

- `POST /collections/{c}/documents` → **`202 Accepted`**,
  응답 `UploadAcceptedResponse { document_id, status: "UPLOADED" }`.
  (이전에는 `201` + `chunk_count` 동기 반환. 임베딩이 비동기라 이제 청크 수를 즉시 못 줌.)
- **신규** `GET /collections/{c}/documents/{id}/status` →
  `DocumentStatusResponse { status, total_chunks, indexed_chunks, filename, error }`.
  프론트가 이걸 폴링해 진행률/완료/실패를 표시.
- 조회/삭제(`GET .../documents`, `.../chunks`, `DELETE`)는 그대로. 삭제는 Qdrant 청크와
  `documents` 레코드를 함께 정리하고 감사 로그(`DocumentManageLog`)를 남깁니다.

`main.py` lifespan에서 시작 시 `ensure_topics` + 프로듀서 `start()`, 종료 시 `close()`를
기존 Qdrant/Redis warmup과 동일 패턴으로 처리합니다.

---

## 7. 인프라 / 실행

**docker-compose** ([`system-docker-compose.yaml`](../system-docker-compose.yaml))에 추가:

- `kafka` — Apache Kafka **KRaft 모드**(Zookeeper 불필요), 단일 브로커. 리스너 2개:
  호스트(백엔드/워커)는 `localhost:9092`, 컨테이너 내부(kafka-ui)는 `kafka:29092`.
- `kafka_ui` — 토픽/메시지/컨슈머 그룹을 보는 웹 UI (`http://localhost:8080`).

**설정** ([`core/config.py`](../backend/app/core/config.py)):

```python
KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
INGEST_MAX_RETRIES: int = 3   # DLQ로 보내기 전 워커 내부 재시도 횟수
```

**실행**(각각 별도 프로세스, 모두 `backend/app`에서):

```bash
docker compose -f system-docker-compose.yaml up -d  # postgres, redis, qdrant, kafka, kafka-ui
uv run uvicorn main:app --reload --port 8000      # API (producer)
uv run python -m workers.parser_worker            # 워커들 (각각 별도 프로세스)
uv run python -m workers.embed_worker
uv run python -m workers.index_worker
```

워커 프로세스를 늘리면(같은 `group_id`) 해당 단계 처리량이 파티션 수 상한까지 수평
확장됩니다.

---

## 8. 프론트엔드 연동

- [`lib/api/documents.ts`](../frontend/src/lib/api/documents.ts) — `ingestDocument`는 이제
  `UploadAcceptedResponse`(202)를 반환, `getDocumentStatus` 추가.
- [`hooks/useDocuments.ts`](../frontend/src/hooks/useDocuments.ts) — `useDocumentStatus`가
  `INDEXED`/`FAILED`에 도달할 때까지 `refetchInterval`로 폴링하고, `INDEXED` 시 문서 목록을
  무효화해 새 문서가 나타나게 함.
- [`pages/DocumentsPage.tsx`](../frontend/src/pages/DocumentsPage.tsx) — 업로드 직후
  진행 배너 표시(`Chunking… → Embedding… → n/m chunks`).

---

## 9. 파일 지도 (이번 추가/변경분)

```
backend/app/
├─ clients/kafka_client.py                     # ★ KafkaProducerClient + ensure_topics
├─ schemes/events/                             # ★ 토픽 상수 + 이벤트 스키마(Pydantic)
│  ├─ topics.py
│  └─ ingestion.py
├─ models/document.py                          # ★ DocumentRecord + DocumentStatus
├─ repositories/document_status_repository.py  # ★ 상태 저장(원자적 진행도 증가)
├─ services/ingestion/
│  ├─ document_service.py                      # ◇ ingest → accept_upload(발행만)
│  ├─ parser_service.py                        # ★ 청킹 → documents.parsed
│  ├─ embed_ingest_service.py                  # ★ 임베딩 → chunks.embed
│  └─ index_service.py                         # ★ Qdrant 적재 + INDEXED
├─ workers/                                    # ★ 별도 프로세스 컨슈머
│  ├─ runner.py                                #   공통 루프(재시도·DLQ·수동 커밋)
│  ├─ parser_worker.py / embed_worker.py / index_worker.py
├─ api/v1/endpoints/documents.py               # ◇ 202 + status 엔드포인트
├─ dependencies/{clients,repositories,services}.py  # ◇ get_* 팩토리 배선
├─ core/config.py                              # ◇ KAFKA_*, INGEST_MAX_RETRIES
└─ main.py                                     # ◇ lifespan: ensure_topics + producer

system-docker-compose.yaml                     # ◇ kafka(KRaft) + kafka-ui
frontend/src/{lib/api/documents.ts, hooks/useDocuments.ts, pages/DocumentsPage.tsx, lib/types.ts}  # ◇

★ 신규  ◇ 변경
```

---

## 10. 동작 시나리오 (end-to-end)

0. (사전) 컬렉션 생성 시 임베딩 모델 선택 → 컬렉션 메타에 고정.
1. 사용자가 `/documents`에 텍스트 업로드 → `accept_upload`가 상태 `UPLOADED` 기록 +
   `documents.uploaded` produce → **즉시 `202`**.
2. **Parser Worker**: 청킹 → `total_chunks` 기록·`PARSING` → 청크마다 `documents.parsed`.
3. **Embed Worker**: 컬렉션 고정 모델로 임베딩(첫 청크에 `EMBEDDING`) → `chunks.embed`.
4. **Index Worker**: `upsert_points`(멱등) → 진행도 원자 증가 → 마지막 청크에서 `INDEXED` +
   성공 이력.
5. 어느 단계든 재시도 소진 → `documents.dlq` + `FAILED`. 프론트는 상태 폴링으로 진행률/실패
   표시.

---

## 11. 검증 방법

```bash
# 1) 인프라 + 워커 기동 (7절)
# 2) 단위 테스트 (backend/app)
uv run pytest                     # 인제스트 서비스/상태 로직 커버
# 3) 컬렉션 생성 후 문서 업로드 → 202 {document_id, status: UPLOADED}
# 4) 상태 폴링: UPLOADED → PARSING → EMBEDDING → INDEXED
#    GET /collections/{c}/documents/{id}/status
# 5) kafka-ui(localhost:8080)에서 토픽별 메시지 흐름 관찰
# 6) 같은 문서 재업로드 → 멱등 upsert(중복 포인트 없음) 확인
# 7) 실패 경로: 잘못된 임베딩 모델/Qdrant 중단 → FAILED + documents.dlq 메시지 확인
```

---

## 12. 남은 과제 (의도적 후속)

- **임베딩 마이크로 배치** — 현재는 메시지당 청크 1개를 임베딩. 처리량/rate limit을 위해
  워커 내부에서 여러 청크를 모아 배치 임베딩하는 것이 가장 큰 성능 레버
  ([RAG_ARCHITECTURE.md](./RAG_ARCHITECTURE.md) §11.2 #1).
- **파일 파싱** — Parser Worker가 실제 PDF/HWP 파싱을 담당할 자리(현재는 청킹만).
- **재임베딩/replay** — 모델 교체 시 원본에서 재produce 또는 offset replay(버전드 컬렉션 권장).
- **보안/운영** — DLQ 접근 제어, 토픽 TLS·인증, 브로커 외부 비노출 등은 운영 전 처리
  ([RAG_ARCHITECTURE.md](./RAG_ARCHITECTURE.md) §11).
```
