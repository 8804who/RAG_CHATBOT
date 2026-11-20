from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.sessions import SessionMiddleware

from api.v1.router import router as api_v1_router
from clients import ensure_topics
from core.config import config
from core.constants import METRICS_PATH
from core.logging_config import configure_logging
from core.model_config.pricing_config import default_pricing_rows
from dependencies.clients import (
    get_kafka_producer,
    get_langfuse_handler,
    get_qdrant_client,
    get_redis_client,
)
from dependencies.repositories import get_pricing_repository
from dependencies.services import (
    get_chat_model_registry,
    get_embedding_registry,
    get_sparse_encoder,
)
from dependencies.db import AsyncSessionLocal
from exceptions.handler import register_exception_handlers
from middlewares import ApiCallLogMiddleware
from schemes.events import ALL_TOPICS

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # 스키마는 Alembic이 관리한다(`uv run alembic upgrade head`를 서버 기동 전에
    # 실행). 과거 create_all()은 이미 존재하는 테이블에는 컬럼을 추가하지 않아
    # 모델이 바뀌어도 조용히 스키마가 어긋나는 문제가 있었다.
    # 모델 단가 기본값 시딩(멱등). 마이페이지 비용 계산 기준값.
    async with AsyncSessionLocal() as session:
        await get_pricing_repository().upsert_defaults(session, default_pricing_rows)
    get_qdrant_client()
    get_redis_client()
    get_embedding_registry()
    get_chat_model_registry()
    get_sparse_encoder()
    get_langfuse_handler()  # None이면 추적 비활성(키 미설정)
    # 인제스트 파이프라인: 토픽 보장 + 프로듀서 시작(API는 발행만, 소비는 워커).
    await ensure_topics(ALL_TOPICS)
    await get_kafka_producer().start()
    yield
    await get_qdrant_client().close()
    await get_redis_client().close()
    await get_kafka_producer().close()


app = FastAPI(title="RAG Chatbot API", lifespan=lifespan)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    session_cookie="oauth_state",
)

# Starlette는 add_middleware를 리스트 앞쪽에 삽입하므로, 가장 바깥쪽(요청 전체
# 수명주기 측정)에 두려면 반드시 마지막에 추가해야 한다.
app.add_middleware(ApiCallLogMiddleware)

# Prometheus HTTP 메트릭(요청 수·지연 히스토그램·처리 중 요청 수). 마지막에 계측해
# 가장 바깥쪽에서 측정한다. 라벨은 라우트 템플릿 기준이라 원시 경로로 카디널리티가
# 폭증하지 않고, 스크레이프 경로 자체는 계측에서 제외한다.
Instrumentator(
    should_instrument_requests_inprogress=True,
    inprogress_labels=True,
    excluded_handlers=[METRICS_PATH],
).instrument(app).expose(app, endpoint=METRICS_PATH, include_in_schema=False)

app.include_router(api_v1_router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "RAG Chatbot API"}
