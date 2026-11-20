# 임베딩 & 컬렉션 관리 코드 설명서

> 대상 독자: **백엔드 1년차** 개발자.
> 이 문서는 `backend/app` 안의 **컬렉션 관리**(Qdrant 벡터 컬렉션 CRUD)와
> **임베딩/문서 인제스트** 코드가 *어떻게 짜여 있고, 왜 그렇게 짰는지*를
> 설명합니다. 실행 흐름을 코드와 함께 따라가고, 사용된 디자인 패턴과 기술을
> 하나씩 풀어 씁니다.
>
> 먼저 읽으면 좋은 문서: [RAG_ARCHITECTURE.md](./RAG_ARCHITECTURE.md) (전체 RAG 그림),
> [CLAUDE.md](../CLAUDE.md) (코드 규칙).

---

## 0. 30초 요약

- 이 코드는 **문서를 벡터로 바꿔(임베딩) Qdrant라는 벡터 DB에 저장**하고, 그
  저장 공간(**컬렉션**)을 만들고 관리하는 부분입니다.
- 구조는 **계층형(Layered)**: `endpoint → service → repository → client`.
  각 계층은 바로 아래 계층만 압니다.
- 객체 연결은 **의존성 주입(DI)** 으로 합니다. FastAPI의 `Depends` +
  `@lru_cache` 싱글톤 팩토리.
- 임베딩 모델은 **provider(OpenAI, fastembed)를 갈아끼울 수 있게** 추상화돼
  있고, `EmbeddingModelRegistry`가 "이름 → 구현체"를 골라줍니다(전략 + 레지스트리 패턴).
- **컬렉션마다 임베딩 모델을 하나로 고정**합니다(`collection_meta` 테이블). 한
  컬렉션의 벡터는 전부 같은 모델/차원이어야 검색이 맞아떨어지기 때문입니다.

---

## 1. 사전 지식: 임베딩과 벡터 DB

코드를 보기 전에 용어 4개만 잡고 갑니다.

### 1.1 임베딩(Embedding)이란

텍스트("고양이는 귀엽다")를 **숫자 배열(벡터)** 로 바꾸는 것입니다.
예: `[0.12, -0.8, 0.33, ...]` (1024개 숫자).
의미가 비슷한 문장은 벡터 공간에서 **가까이** 위치합니다. 그래서 "질문 벡터와
가까운 문서 벡터"를 찾으면 = 의미가 비슷한 문서를 찾는 검색이 됩니다.

- **dense(밀집) 벡터**: 위 예시처럼 모든 칸이 채워진 벡터. **의미 유사도**에 강함.
- **sparse(희소) 벡터**: 대부분 0이고 일부 단어 위치만 값이 있는 벡터. **정확한
  단어 매칭**(제품명, 에러코드)에 강함. (BM25 방식)
- **하이브리드 검색**: dense + sparse를 **둘 다** 써서 서로의 약점을 가립니다.

### 1.2 벡터 DB / Qdrant

벡터를 저장하고 "가장 가까운 N개"를 빠르게 찾아주는 특수 DB입니다. 이
프로젝트는 **Qdrant**를 씁니다(`system-docker-compose.yaml`의 `:6333`).

### 1.3 컬렉션(Collection)

Qdrant에서 벡터들을 담는 **테이블 같은 단위**입니다. 컬렉션을 만들 때
"벡터 차원은 1024, 거리 계산은 코사인" 같은 규칙을 정합니다.

### 1.4 포인트(Point)

컬렉션에 들어가는 **한 줄(row)** 입니다. `id + 벡터 + payload(부가 정보)`로
구성됩니다. 이 프로젝트에선 **문서 청크 1개 = 포인트 1개**이고, payload에
`document_id`, `filename`, `chunk_index`, `text` 등을 담습니다.

---

## 2. 큰 그림: 계층형 아키텍처

모든 요청은 **위에서 아래로** 한 방향으로 흐릅니다.

```
HTTP 요청
   │
   ▼
┌──────────────┐  api/v1/endpoints/*.py
│  Endpoint    │  · HTTP만 안다(요청 파싱, 응답 직렬화, 예외→상태코드)
└──────┬───────┘  · 비즈니스 로직 없음
       │ Depends(get_*_service)
       ▼
┌──────────────┐  services/*.py
│  Service     │  · 비즈니스 로직(검증, 조합, 순서 제어)
└──────┬───────┘  · "임베딩 모델이 등록됐나?", "청킹 후 임베딩 후 적재"
       │ 생성자 주입
       ▼
┌──────────────┐  repositories/*.py
│  Repository  │  · 저장소 접근(Qdrant/Postgres) 전담
└──────┬───────┘  · 도메인 타입 ↔ qdrant_client 타입 변환
       │ 생성자 주입
       ▼
┌──────────────┐  clients/*.py
│  Client      │  · 외부 라이브러리/서비스 래핑(AsyncQdrantClient, OpenAI…)
└──────────────┘
```

**왜 이렇게 나누나요?** (1년차가 가장 궁금한 부분)

- **책임 분리**: endpoint는 HTTP만, service는 로직만, repository는 DB만 신경
  씁니다. 한 파일이 너무 많은 걸 알지 않게 됩니다.
- **테스트 용이**: service를 테스트할 때 repository를 **가짜(mock)** 로
  갈아끼우면 진짜 Qdrant 없이 로직만 검증할 수 있습니다.
  ([tests/services/test_document_service.py](../backend/tests/services/test_document_service.py)가 정확히 이렇게 합니다.)
- **교체 용이**: Qdrant를 다른 벡터 DB로 바꿔도 repository/client만 갈면 service는
  그대로입니다.

> **핵심 규칙**: 계층은 **바로 아래만** 의존합니다. endpoint가 repository를 직접
> 부르거나, service가 `AsyncQdrantClient`를 직접 쓰면 안 됩니다.

---

## 3. 파일 지도

```
backend/app/
├─ api/v1/
│  ├─ router.py                         # 하위 라우터들을 한데 모음
│  └─ endpoints/
│     ├─ collections.py                 # 컬렉션 CRUD 엔드포인트
│     ├─ documents.py                   # 문서 인제스트/조회 엔드포인트
│     └─ models.py                      # GET /models (모델 카탈로그)
│
├─ services/
│  ├─ vector_db/
│  │  ├─ vector_db_service.py           # 추상 베이스(VectorDBService)
│  │  └─ qdrant_service.py              # 컬렉션 관리 비즈니스 로직
│  ├─ embedding/
│  │  └─ embedding_service.py           # 텍스트 → dense(+sparse) 임베딩 조합
│  ├─ ingestion/
│  │  ├─ chunker.py                     # 긴 텍스트 → 청크 분할
│  │  └─ document_service.py            # 인제스트 오케스트레이션
│  └─ model_registry.py                 # 임베딩 모델 카탈로그 + 라우팅
│
├─ repositories/
│  ├─ vector_db/
│  │  ├─ vector_db_repository.py        # 추상 베이스(VectorDBRepository)
│  │  └─ qdrant_repository.py           # Qdrant 접근 전담
│  └─ collection_meta_repository.py     # 컬렉션→임베딩모델 매핑(Postgres)
│
├─ clients/
│  ├─ qdrant_db_client.py               # AsyncQdrantClient 래퍼
│  └─ embedding/
│     ├─ embedding_client.py            # 추상 베이스(EmbeddingClient)
│     ├─ fastembed_embedding_client.py  # 로컬 모델 구현
│     ├─ openai_embedding_client.py     # OpenAI API 구현
│     └─ sparse_encoder.py              # BM25 sparse 인코더
│
├─ models/collection_meta.py            # SQLAlchemy 테이블 정의
├─ schemes/
│  ├─ requests.py / responses.py        # API 입출력 스키마(Pydantic)
│  └─ dto/embedding.py, document.py, qdrant.py  # 계층 간 이동 타입
│
├─ dependencies/                        # DI 팩토리(@lru_cache 싱글톤)
│  ├─ clients.py / repositories.py / services.py
└─ exceptions/                          # 커스텀 예외 + 전역 핸들러
```

---

## 4. 컬렉션 관리 흐름 따라가기

"컬렉션 생성"(`POST /api/v1/collections`)을 위에서 아래로 따라가 봅니다.

### 4.1 Endpoint — HTTP 경계

[api/v1/endpoints/collections.py](../backend/app/api/v1/endpoints/collections.py)

```python
@router.post("")
async def create_collection(
    collection_info: CreateQdrantCollectionRequest,          # ① 요청 본문 검증
    qdrant_service: QdrantService = Depends(get_qdrant_service),  # ② 서비스 주입
    db: AsyncSession = Depends(get_db_session),                   # ③ DB 세션 주입
):
    result = await qdrant_service.create_collections(             # ④ 서비스에 위임
        db=db, collection_info=collection_info
    )
    return result
```

- ① **요청 검증은 타입이 알아서**: 파라미터 타입을 `CreateQdrantCollectionRequest`
  (Pydantic 모델)로 선언하면, FastAPI가 JSON을 파싱하고 검증해서 넣어줍니다.
  형식이 틀리면 endpoint 코드가 실행되기 전에 자동으로 422를 반환합니다.
- ② `Depends(get_qdrant_service)`: "이 서비스가 필요해" 하면 FastAPI가 만들어
  넣어줍니다(= 의존성 주입). 직접 `QdrantService(...)`를 만들지 않습니다.
- ④ endpoint는 **로직을 직접 하지 않고** 서비스에 넘깁니다. endpoint가 얇은 게
  좋은 신호입니다.

> **예외는 어디서?** endpoint에 `try/except`가 없습니다. service/repository에서
> 던진 커스텀 예외를 **전역 핸들러**가 받아서 HTTP 응답으로 바꿔줍니다(7장 참고).

### 4.2 Service — 비즈니스 규칙

[services/vector_db/qdrant_service.py](../backend/app/services/vector_db/qdrant_service.py)

```python
async def create_collections(self, db, collection_info) -> bool:
    model = collection_info.embedding_model
    # (1) 등록된 모델인가? 아니면 UnsupportedEmbeddingModelError(400)
    registered = self._embedding_registry.get_info(model.name)
    # (2) 요청 차원이 모델 실제 차원과 같은가?
    if registered.dimension != model.dimension:
        raise EmbeddingModelDimensionMismatchError(...)
    # (3) Qdrant에 실제 컬렉션 생성
    result = await self._qdrant_repository.create_collections(collection_info)
    # (4) "이 컬렉션은 이 모델을 쓴다"를 Postgres에 영구 저장
    await self._collection_meta_repository.create(
        db, collection_name=collection_info.collection_name,
        embedding_model=model.name, dimension=model.dimension,
    )
    return result
```

이 서비스가 하는 일은 **"순서대로 검증하고 조합"** 입니다.

- (1)~(2) **검증**: 아무 모델 이름이나 받지 않고, 레지스트리에 등록된
  화이트리스트만 허용합니다. 차원이 안 맞으면 나중에 임베딩 적재가 실패하므로
  **미리** 막습니다.
- (3) Qdrant 작업은 repository에 위임.
- (4) **컬렉션 ↔ 임베딩 모델 매핑을 저장**합니다. 이게 이 설계의 핵심:
  한 컬렉션의 벡터는 전부 같은 모델로 만들어야 검색이 일관됩니다. 그래서 생성
  시점에 모델을 못 박아 두고, 나중 인제스트/질의는 이 값을 강제로 씁니다.

> **두 저장소에 나눠 저장**: 컬렉션의 "벡터 데이터"는 Qdrant에, "이 컬렉션이 어떤
> 모델을 쓰는지"라는 메타데이터는 Postgres에 둡니다. Qdrant는 벡터 검색 전용이고
> 관계형 메타 관리는 Postgres가 낫기 때문입니다.

### 4.3 Repository — 저장소 접근 + 타입 변환

[repositories/vector_db/qdrant_repository.py](../backend/app/repositories/vector_db/qdrant_repository.py)

```python
async def create_collections(self, request) -> bool:
    if await self._qdrant_client.client.collection_exists(request.collection_name):
        raise CollectionAlreadyExistsError(...)            # 중복이면 409

    # 우리 도메인 타입(DenseVectorConfig) → qdrant_client 타입(models.VectorParams)
    vectors_config = {
        name: models.VectorParams(
            size=cfg.size,
            distance=models.Distance(cfg.distance.value),
            on_disk=cfg.on_disk,
        )
        for name, cfg in request.dense_vectors.items()
    }
    ...
    return await self._qdrant_client.client.create_collection(...)
```

repository의 중요한 역할: **우리 코드의 타입 ↔ 외부 라이브러리 타입 변환**.
`qdrant_client.models.*` 같은 라이브러리 전용 타입을 **여기 한 곳에만** 가둬서,
서비스/엔드포인트는 Qdrant SDK를 몰라도 되게 합니다.

### 4.4 Client — 외부 의존성 래핑

[clients/qdrant_db_client.py](../backend/app/clients/qdrant_db_client.py)

```python
class QdrantDBClient:
    def __init__(self):
        self.client = AsyncQdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY)
    async def close(self) -> None:
        await self.client.close()
```

`AsyncQdrantClient`를 클래스로 한 겹 감쌌습니다. 연결 설정(`config`)과 정리(`close`)를
한 곳에 모으고, 앱 시작/종료 시 생명주기를 관리하기 위해서입니다.

### 4.5 컬렉션 조회/수정/삭제

같은 4단계 흐름을 따릅니다. 몇 가지만 짚으면:

- `GET /collections/{name}`은 Qdrant의 벡터 설정에 더해, **이 컬렉션에 고정된
  임베딩 모델**을 `collection_meta`에서 읽어 함께 반환합니다(프론트가 표시용).
- `DELETE`는 Qdrant 컬렉션을 지운 뒤 `collection_meta` 매핑도 지웁니다(두 저장소
  정합성 유지).
- `update`는 Qdrant 제약상 **벡터 size/distance는 변경 불가**라, 수정 가능한
  항목(on_disk, optimizer)만 노출합니다 — [requests.py](../backend/app/schemes/requests.py)의
  `UpdateQdrantCollectionRequest` 참고.

---

## 5. 임베딩 & 문서 인제스트 흐름 따라가기

이제 핵심. "문서 업로드"(`POST /api/v1/collections/{name}/documents`)가 어떻게
임베딩되어 저장되는지 봅니다.

### 5.1 전체 그림

```
문서 텍스트
   │  DocumentService.ingest()
   ▼
[1] collection_meta 조회 → 이 컬렉션이 쓸 임베딩 모델 확인
[2] Qdrant 컬렉션 설정 조회 → dense/sparse "벡터 이름" 확보
[3] 청킹(chunk_text) → 긴 글을 여러 조각으로
[4] EmbeddingService.embed_documents() → 조각마다 dense(+sparse) 벡터 생성
[5] 청크마다 IngestPoint 구성(벡터 + payload)
[6] QdrantRepository.upsert_points() → Qdrant에 적재
   ▼
DocumentSummary(document_id, chunk_count) 반환
```

### 5.2 DocumentService — 오케스트레이터

[services/ingestion/document_service.py](../backend/app/services/ingestion/document_service.py)

```python
async def ingest(self, db, collection_name, filename, content) -> DocumentSummary:
    # [1] 이 컬렉션이 어떤 임베딩 모델을 쓰는지(생성 시 고정한 값)
    meta = await self._collection_meta_repository.get(db, collection_name)
    if meta is None:
        raise CollectionMetaNotFoundError(...)   # 우리 흐름으로 안 만든 컬렉션

    # [2] Qdrant 컬렉션의 벡터 이름 확보(적재 시 이름이 일치해야 함)
    detail = await self._qdrant_repository.get_collection(collection_name)
    dense_name = next(iter(detail.dense_vectors), None)
    sparse_name = next(iter(detail.sparse_vectors), None)
    with_sparse = sparse_name is not None

    # [3] 청킹
    chunks = chunk_text(content)
    if not chunks:
        raise EmptyDocumentError(...)

    # [4] 임베딩 (컬렉션에 고정된 모델 이름을 강제 사용)
    results = await self._embedding_service.embed_documents(
        meta.embedding_model, chunks, with_sparse=with_sparse
    )

    # [5] 청크마다 포인트 구성 (한 문서의 청크들은 같은 document_id로 묶음)
    document_id = uuid4().hex
    points = [
        IngestPoint(
            id=uuid4().hex, dense=r.dense,
            payload={"document_id": document_id, "filename": filename,
                     "chunk_index": i, "text": chunk, "created_at": ...},
            dense_vector_name=dense_name,
            sparse=r.sparse if with_sparse else None,
            sparse_vector_name=sparse_name,
        )
        for i, (chunk, r) in enumerate(zip(chunks, results, strict=True))
    ]
    # [6] 적재
    await self._qdrant_repository.upsert_points(collection_name, points)
    return DocumentSummary(document_id, filename, len(chunks), created_at)
```

**"오케스트레이터"** 라는 말이 핵심입니다. 이 서비스는 스스로 임베딩하지도, 직접
Qdrant에 쓰지도 않습니다. 대신 **"누구를 어떤 순서로 부를지"** 만 결정합니다.
임베딩은 `EmbeddingService`에, 저장은 `QdrantRepository`에 위임합니다.

> **왜 service가 다른 service(`EmbeddingService`)를 부르나?** 계층 규칙은
> "아래만 의존"이지만, **같은 계층(service)끼리 조합**하는 건 흔하고 정상입니다.
> `DocumentService`는 상위 오케스트레이터, `EmbeddingService`는 재사용 가능한
> 하위 기능입니다(질의 임베딩에서도 같은 `EmbeddingService`를 씁니다).

### 5.3 청킹 — 왜 자르나

[services/ingestion/chunker.py](../backend/app/services/ingestion/chunker.py)

LLM/임베딩 모델은 한 번에 처리할 수 있는 길이에 한계가 있고, **검색은 "조각"
단위로 해야 정확**합니다(책 한 권 통째 vs 관련 문단). 그래서 긴 글을 단어 기준
**슬라이딩 윈도우**로 자릅니다.

```python
def chunk_text(text, chunk_size=400, overlap=80) -> list[str]:
    words = text.split()
    step = chunk_size - overlap          # 80단어 겹치며 400단어씩
    ...
```

`overlap`(겹침)을 두는 이유: 조각 경계에서 문맥이 잘려 의미가 깨지는 걸 줄이기
위해서입니다.

### 5.4 EmbeddingService — dense + sparse 조합

[services/embedding/embedding_service.py](../backend/app/services/embedding/embedding_service.py)

```python
async def embed_documents(self, model_name, texts, with_sparse=True):
    client = self._embedding_registry.resolve(model_name)   # 이름 → 구현체
    dense_vectors = await client.embed_documents(texts)     # dense는 선택된 provider
    sparse_vectors = (await self._sparse_encoder.encode_documents(texts)
                      if with_sparse else [None] * len(texts))   # sparse는 공통 BM25
    return [EmbeddingResult(dense=d, sparse=s)
            for d, s in zip(dense_vectors, sparse_vectors, strict=True)]
```

여기서 두 가지를 합칩니다.
- **dense**: `model_name`으로 레지스트리에서 고른 provider(OpenAI or fastembed).
- **sparse**: provider와 무관하게 **공통 BM25 인코더**.

`EmbeddingService`는 **어떤 provider인지 모릅니다.** 그냥 "resolve로 받은 client의
`embed_documents`를 호출"할 뿐입니다. 이게 다음 장의 핵심 패턴입니다.

### 5.5 임베딩 모델 추상화 (가장 중요한 설계)

provider(임베딩 제공자)를 갈아끼울 수 있게 만든 구조입니다.

**(1) 공통 인터페이스** — [clients/embedding/embedding_client.py](../backend/app/clients/embedding/embedding_client.py)

```python
class EmbeddingClient(ABC):           # 추상 베이스(계약서)
    @abstractmethod
    async def embed_documents(self, texts) -> list[list[float]]: ...
    @abstractmethod
    async def embed_query(self, text) -> list[float]: ...
    @abstractmethod
    async def warmup(self) -> None: ...
```

**(2) 구현체들** — 같은 인터페이스를 각자 다르게 구현

- [fastembed_embedding_client.py](../backend/app/clients/embedding/fastembed_embedding_client.py):
  로컬에서 모델을 돌림(API 키·비용 없음, 대신 모델 로딩이 무거움).
- [openai_embedding_client.py](../backend/app/clients/embedding/openai_embedding_client.py):
  OpenAI API 호출(키 필요, 비용 있음, 로컬 로딩 없음).

**(3) 레지스트리** — [services/model_registry.py](../backend/app/services/model_registry.py)

```python
class EmbeddingModelRegistry:
    def __init__(self, catalog: dict[str, tuple[RegisteredEmbeddingModel, EmbeddingClient]]):
        self._catalog = catalog        # "모델 이름" → (메타정보, 구현체)

    def resolve(self, model_name) -> EmbeddingClient:   # 이름 → 구현체
        entry = self._catalog.get(model_name)
        if entry is None:
            raise UnsupportedEmbeddingModelError(...)
        return entry[1]
```

**무엇을 노출할지**는 [dependencies/services.py](../backend/app/dependencies/services.py)의
`get_embedding_registry()` 한 곳에서 결정합니다:

```python
catalog = {
    "BAAI/bge-m3":            (RegisteredEmbeddingModel(..., dimension=1024), fastembed_bge_m3),
    "text-embedding-3-small": (RegisteredEmbeddingModel(..., dimension=1536), openai_small),
    "text-embedding-3-large": (RegisteredEmbeddingModel(..., dimension=3072), openai_large),
}
```

이 구조 덕분에 **새 provider 추가 = 파일 하나 + 카탈로그 한 줄**. 서비스/엔드포인트
코드는 한 글자도 안 바뀝니다. (= OCP, 개방-폐쇄 원칙)

### 5.6 Repository — Qdrant 적재/조회/삭제

[repositories/vector_db/qdrant_repository.py](../backend/app/repositories/vector_db/qdrant_repository.py)
에 추가된 포인트 단위 메서드들:

- `upsert_points`: `IngestPoint`(우리 타입)들을 `models.PointStruct`(Qdrant 타입)로
  변환해 적재. **upsert** = 같은 id면 덮어쓰기 → 재실행해도 중복이 안 쌓임(멱등성).
- `scroll_points`: 컬렉션 포인트를 **페이지 단위로 전량** 읽음. `document_id` 필터를
  주면 특정 문서의 청크만. (`while` 루프로 `offset`을 따라가며 256개씩)
- `delete_by_document`: payload의 `document_id`가 일치하는 포인트를 필터로 삭제.

`DocumentService.list_documents`는 `scroll_points`로 모든 청크를 읽어 **payload의
`document_id`로 그룹핑**해서 "문서 목록 + 청크 수"를 만듭니다. (DB의 GROUP BY를
애플리케이션에서 손으로 하는 셈)

---

## 6. 사용된 디자인 패턴 총정리

| 패턴 | 어디에 | 한 줄 설명 |
|---|---|---|
| **Layered Architecture** | 전체 | endpoint→service→repository→client 단방향 의존 |
| **Dependency Injection(DI)** | `dependencies/*`, `Depends`, 생성자 주입 | 객체를 직접 만들지 않고 **밖에서 넣어줌** → 교체·테스트 용이 |
| **Singleton + Factory** | `@lru_cache get_*()` | 무상태 서비스/레포는 앱당 1개만 만들어 재사용 |
| **Repository Pattern** | `*_repository.py` | 저장소 접근을 한 계층에 격리, 비즈니스 로직과 분리 |
| **Strategy Pattern** | `EmbeddingClient` + 구현체들 | 같은 인터페이스, 런타임에 알고리즘(provider) 교체 |
| **Registry Pattern** | `EmbeddingModelRegistry` | "이름 → 구현체" 매핑을 한 곳에서 관리·검증 |
| **Adapter/Wrapper** | `clients/*` | 외부 SDK(Qdrant, OpenAI)를 우리 인터페이스로 감쌈 |
| **Abstract Base(Template)** | `VectorDBService`, `EmbeddingClient` 등 | 하위 클래스가 지켜야 할 **계약(메서드 시그니처)** 강제 |
| **DTO / Schema 분리** | `schemes/requests·responses·dto` | 계층마다 알맞은 타입으로 데이터 이동 |
| **Orchestrator(Facade)** | `DocumentService` | 여러 하위 기능을 순서대로 조합하는 상위 진입점 |

### 6.1 DI를 조금 더 — `@lru_cache` 싱글톤

[dependencies/services.py](../backend/app/dependencies/services.py)

```python
@lru_cache
def get_qdrant_service() -> QdrantService:
    return QdrantService(
        qdrant_repository=get_qdrant_repository(),
        embedding_registry=get_embedding_registry(),
        collection_meta_repository=get_collection_meta_repository(),
    )
```

- `@lru_cache`: 같은 인자로 다시 부르면 **이전 결과를 그대로** 돌려줍니다.
  인자가 없으니 결국 **앱 전체에서 1개 인스턴스**(싱글톤)가 됩니다.
- 서비스/레포는 **상태가 없어서**(요청별 데이터를 인스턴스에 저장 안 함) 공유해도
  안전합니다. 요청별로 다른 건 `db`(세션)인데, 그건 **메서드 인자로** 따로 받습니다.
- 의존 객체(`get_qdrant_repository()` 등)도 같은 방식이라 → **의존성 그래프가
  팩토리 함수들로 조립**됩니다. FastAPI의 `Depends(get_qdrant_service)`가 이
  최상단 팩토리를 호출해 트리거합니다.

### 6.2 추상 베이스는 왜 두 쌍이나 있나

`VectorDBService`(추상) ← `QdrantService`(구현),
`VectorDBRepository`(추상) ← `QdrantRepository`(구현).

지금은 구현이 Qdrant 하나뿐이라 "왜 추상이 필요하지?" 싶을 수 있습니다. 이유:
- **계약 명시**: "벡터 DB 서비스라면 이 메서드들은 반드시 있어야 한다"를 코드로
  강제합니다(`@abstractmethod`).
- **확장 대비**: 나중에 `WeaviateService`를 추가해도 같은 인터페이스를 따르면
  상위 코드는 그대로입니다.
- 다만 **YAGNI 균형**도 알아두세요 — 영영 한 개뿐이라면 추상은 과할 수 있습니다.
  이 프로젝트는 "provider 교체 가능성"을 1급 요구사항으로 보고 둔 선택입니다.

---

## 7. 예외 처리 구조

[exceptions/base.py](../backend/app/exceptions/base.py)

```python
class AppException(Exception):
    status_code: int          # HTTP 상태코드
    response_message: str     # 프론트에 보여줄 메시지

    def __init__(self, message, code_path):
        self.message = message      # 내부 로그용 상세
        self.code_path = code_path  # "파일-함수-error" 형식, 어디서 터졌는지
```

- 도메인 예외는 모두 이걸 상속합니다. 예:
  [exceptions/embedding.py](../backend/app/exceptions/embedding.py)의
  `UnsupportedEmbeddingModelError(400)`,
  [exceptions/document.py](../backend/app/exceptions/document.py)의
  `CollectionMetaNotFoundError(400)`,
  [exceptions/vector_db.py](../backend/app/exceptions/vector_db.py)의
  `CollectionNotFoundError(404)`.
- **service/repository에서 던지고, endpoint는 안 잡습니다.**
  [exceptions/handler.py](../backend/app/exceptions/handler.py)의 전역 핸들러가
  `AppException`을 받아 `status_code` + `message`로 JSON 응답을 만듭니다.

```python
async def app_exception_handler(request, exc: AppException):
    logger.error("%s\n오류 발생 위치: %s", exc.message, exc.code_path)  # 상세는 로그만
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
```

**왜 이렇게?**
- endpoint마다 `try/except`를 도배하지 않아도 됩니다(한 곳에서 처리).
- **내부 정보(`code_path`, 스택)는 로그로만**, 프론트엔드엔 깔끔한 메시지만
  나갑니다(보안).

---

## 8. 데이터가 흐르는 타입들

같은 "컬렉션 정보"라도 계층마다 **다른 타입**을 씁니다. 헷갈리기 쉬워서 정리합니다.

| 종류 | 위치 | 예시 | 용도 |
|---|---|---|---|
| **Request 스키마** | `schemes/requests.py` | `CreateQdrantCollectionRequest` | API 입력 검증(Pydantic) |
| **Response 스키마** | `schemes/responses.py` | `CollectionDetailResponse` | API 출력 직렬화(Pydantic) |
| **DTO** | `schemes/dto/*` | `CollectionDetail`, `IngestPoint`, `EmbeddingResult` | 계층 간 이동용 내부 타입(dataclass) |
| **ORM 모델** | `models/*` | `CollectionMeta` | DB 테이블 매핑(SQLAlchemy) |

**왜 분리하나?** API에 노출할 모양(Response), 내부에서 다룰 모양(DTO), DB에 저장할
모양(ORM)이 **서로 달라야 자유롭습니다.** 예를 들어 DB 컬럼을 바꿔도 API 응답
형태는 그대로 둘 수 있고, 그 반대도 됩니다. (= 결합도 낮춤)

> 작은 팁: Response 모델의 `model_config = ConfigDict(from_attributes=True)`는
> "dataclass/ORM 객체의 **속성**을 보고 만들어도 된다"는 설정입니다. 그래서
> service가 `CollectionDetail`(dataclass)을 반환해도 FastAPI가
> `CollectionDetailResponse`로 자동 변환합니다.

---

## 9. 사용된 기술 한눈에

| 기술 | 역할 | 이 코드에서 |
|---|---|---|
| **FastAPI** | 웹 프레임워크 | 라우팅, `Depends` DI, 요청 검증 |
| **Pydantic** | 데이터 검증/직렬화 | request/response 스키마 |
| **pydantic-settings** | 환경설정 로딩 | [core/config.py](../backend/app/core/config.py)의 `config` |
| **SQLAlchemy (async)** | ORM | `CollectionMeta`, `AsyncSession` |
| **asyncpg** | 비동기 Postgres 드라이버 | DB 연결 |
| **Qdrant (AsyncQdrantClient)** | 벡터 DB | 컬렉션/포인트 |
| **fastembed** | 로컬 임베딩 | bge-m3(dense), bm25(sparse) |
| **openai** | 원격 임베딩 | text-embedding-3-* |
| **anyio** | async 유틸 | 무거운 동기 작업을 스레드풀로(`to_thread`) |

### 9.1 async / await 한 줄 정리

이 코드는 거의 다 `async def`입니다. 이유: 임베딩 API 호출, Qdrant 조회, DB 조회는
**대기(I/O)가 많은 작업**입니다. `await`로 기다리는 동안 **다른 요청을 처리**할 수
있어 적은 자원으로 많은 동시 요청을 받습니다.

단, **fastembed 모델 추론은 동기 + CPU 무거운 작업**입니다. 이걸 그냥 `async`
함수에서 직접 부르면 이벤트 루프가 멈춰 다른 요청이 다 막힙니다. 그래서:

```python
return await anyio.to_thread.run_sync(_run)   # 별도 스레드에서 실행
```

무거운 동기 작업을 **스레드풀로 밀어** 이벤트 루프를 막지 않습니다.

---

## 10. 임베딩 모델 선로딩(Warmup) — Lazy vs Eager

fastembed 로컬 모델은 **수백 MB~GB를 메모리에 로딩**해야 첫 사용이 가능합니다.
처음엔 "필요할 때 로딩"(lazy)했지만, **앱 시작 시 미리 로딩**(eager)으로 바꿨습니다.

```python
# clients/embedding/fastembed_embedding_client.py
async def warmup(self) -> None:
    await anyio.to_thread.run_sync(self._ensure_model)   # 시작 시 모델 로드
```

```python
# main.py 의 lifespan (앱 시작/종료 훅)
await get_embedding_registry().warmup()   # 등록된 dense 모델들 선로딩
await get_sparse_encoder().warmup()       # sparse 모델 선로딩
```

- **Lazy(지연)**: 시작은 빠르지만 **첫 임베딩 요청이 느림**(그때 로딩).
- **Eager(선로딩)**: 시작이 느려지는 대신 **첫 요청부터 빠름**, 사용자 체감 안정적.

레지스트리의 `warmup()`은 provider별로 실패를 **격리**합니다. 예를 들어
`OPENAI_API_KEY`가 없으면 OpenAI client 생성은 실패하는데, 그걸로 앱 전체 시작이
죽지 않도록 경고만 로깅하고 나머지(로컬 모델)는 계속 로딩합니다.

```python
for info, client in self._catalog.values():
    try:
        await client.warmup()
    except Exception as error:           # provider별 실패 격리
        logger.warning("embedding_model_registry-warmup-error: model=%s ...", info.name)
```

> 이건 **트레이드오프**입니다: 안정적인 첫 응답 ↔ 느린 부팅 + 높은 초기 메모리.
> 등록된 로컬 모델이 많아질수록 부팅 비용이 커집니다.

---

## 11. 테스트는 어떻게 짜였나

[tests/services/test_document_service.py](../backend/tests/services/test_document_service.py)
가 DI/계층 분리의 **실익**을 잘 보여줍니다.

```python
def _make_service():
    qdrant_repo = AsyncMock()            # 진짜 Qdrant 대신 가짜
    embedding_service = AsyncMock()      # 진짜 임베딩 대신 가짜
    meta_repo = AsyncMock()
    return DocumentService(qdrant_repo, embedding_service, meta_repo), ...
```

- 생성자로 의존성을 주입하니, 테스트에서 **가짜(AsyncMock)** 를 넣기 쉽습니다.
- 그래서 Qdrant·임베딩 모델 없이 **로직만**(그룹핑이 맞나, 빈 입력에 예외가 나나)
  빠르게 검증합니다.
- 네이밍 규칙: `test_<함수>_<success|failed>_with_<상황>` — 예
  `test_ingest_failed_with_missing_meta`.

실행:
```bash
cd backend/app
uv run pytest                 # 전체
uv run pytest -k document     # 이름에 document 포함된 것만
```

---

## 12. 추가 사항 · 주의점 · 개선 여지

1년차가 코드를 더 발전시킬 때 알아두면 좋은 것들.

1. **지금 인제스트는 동기(synchronous)** 입니다. 업로드 요청 안에서 청킹·임베딩·적재를
   전부 끝내고 응답합니다. 큰 문서면 응답이 오래 걸립니다.
   → [RAG_ARCHITECTURE.md](./RAG_ARCHITECTURE.md)는 이를 **Kafka로 비동기화**하는
   설계를 제시합니다(업로드는 즉시 202, 워커가 뒤에서 처리). 현재는 의도적으로
   단순한 MVP입니다.

2. **파일 파싱이 없습니다.** 프론트가 텍스트를 읽어 보내는 구조라 `.txt/.md` 위주.
   PDF/HWP 파싱은 추후 과제.

3. **payload 인덱스**: `scroll_points`/`delete_by_document`가 payload의
   `document_id`로 필터링하는데, 데이터가 커지면 Qdrant에 payload 인덱스를 만들어야
   빨라집니다(지금은 전체 스캔).

4. **`collection_meta`와 Qdrant의 정합성**: 두 저장소에 나눠 저장하므로, 한쪽만
   성공하고 다른 쪽이 실패하면 어긋날 수 있습니다(분산 트랜잭션 문제). 삭제 시
   순서·실패 처리에 유의하세요.

5. **벡터 이름 의존**: 인제스트가 컬렉션의 "첫 번째 dense/sparse 벡터 이름"을
   사용합니다(`next(iter(...))`). 프론트의
   [CreateCollectionForm](../frontend/src/components/collections/CreateCollectionForm.tsx)은
   관례적으로 `dense`/`sparse`라는 이름을 씁니다. 컬렉션을 다른 도구로 만들면
   이름이 달라질 수 있으니 주의.

6. **import 루트는 `backend/app`** 입니다. `from services...`처럼 루트 상대 경로로
   import하고, 실행/테스트도 그 디렉터리에서 합니다([CLAUDE.md](../CLAUDE.md)).

7. **주석/독스트링은 한국어**, 포맷은 `uv run ruff format .`, 변경 후 테스트 추가가
   이 레포의 규칙입니다.

---

## 부록 A. 한 요청의 전체 호출 스택 (인제스트)

```
POST /api/v1/collections/my-docs/documents      {filename, content}
  └─ endpoints/documents.py : ingest_document()
       └─ DocumentService.ingest(db, "my-docs", filename, content)
            ├─ CollectionMetaRepository.get(db, "my-docs")        → embedding_model 확인
            ├─ QdrantRepository.get_collection("my-docs")         → 벡터 이름 확인
            ├─ chunk_text(content)                                → ["청크1", "청크2", ...]
            ├─ EmbeddingService.embed_documents(model, chunks)
            │    ├─ EmbeddingModelRegistry.resolve(model)         → EmbeddingClient 선택
            │    ├─ client.embed_documents(chunks)                → dense 벡터들
            │    └─ BM25SparseEncoder.encode_documents(chunks)    → sparse 벡터들
            └─ QdrantRepository.upsert_points("my-docs", points)  → Qdrant 적재
  ← 201  {document_id, filename, chunk_count, created_at}
```

## 부록 B. 자주 나오는 질문

- **Q. service에서 `db`를 왜 인자로 받나요? 생성자에 안 넣고?**
  A. DB 세션은 **요청마다 새로 만들어 닫는** 짧은 수명입니다. 싱글톤 서비스에
  박아두면 안 됩니다. 그래서 서비스는 싱글톤으로 공유하되, `db`만 요청 시
  메서드 인자로 받습니다.

- **Q. `EmbeddingClient`는 client인데 왜 `clients/`가 아니라 일부는 service가 쓰나요?**
  A. `clients/embedding/*`(구현체)는 client 계층이 맞습니다. `EmbeddingService`가
  `EmbeddingModelRegistry`를 통해 그 client를 **간접적으로** 씁니다. 즉
  service → (registry) → client 로 내려갑니다.

- **Q. dense/sparse를 꼭 둘 다 써야 하나요?**
  A. 아닙니다. 컬렉션에 sparse 벡터를 안 만들면 `with_sparse=False`로 dense만
  적재합니다. 하이브리드 검색 품질을 위해 둘 다 쓰길 권장할 뿐입니다.
