from functools import lru_cache

from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from clients import KafkaProducerClient, QdrantDBClient, RedisClient
from core.config import config
from core.constants import CHECKPOINTER_POOL_MAX_SIZE


@lru_cache
def get_qdrant_client():
    return QdrantDBClient()


@lru_cache
def get_redis_client():
    return RedisClient()


@lru_cache
def get_kafka_producer() -> KafkaProducerClient:
    return KafkaProducerClient()


@lru_cache
def get_langfuse_handler() -> CallbackHandler | None:
    """
    Langfuse 콜백 핸들러(에이전트 실행 추적)

    public/secret key가 모두 설정된 경우에만 핸들러를 만든다(둘 중 하나라도
    없으면 추적을 생략하고 None 반환 — 다른 optional provider와 동일한 패턴).
    """
    if not config.LANGFUSE_PUBLIC_KEY or not config.LANGFUSE_SECRET_KEY:
        return None
    return CallbackHandler()


def checkpointer_conninfo() -> str:
    """
    체크포인터용 Postgres 접속 문자열 생성

    URL f-string 대신 key=value 형식으로 만들어, 비밀번호의 @ / # % 같은 예약
    문자가 그대로 전달된다(CR-012 F8).

    Returns:
        str: libpq conninfo 문자열
    """
    return make_conninfo(
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        dbname=config.POSTGRES_DB,
    )


@lru_cache
def get_checkpointer() -> AsyncPostgresSaver:
    """
    LangGraph 체크포인터(채팅 스레드별 에이전트 상태 = 멀티턴 대화 이력 저장)

    psycopg 커넥션 풀 위에 만든다(단일 커넥션은 끊기면 복구 불가). 풀은 닫힌 채로
    생성되며 lifespan에서 open()·setup()(체크포인트 테이블 생성, 멱등) 후 사용한다.
    """
    pool = AsyncConnectionPool(
        conninfo=checkpointer_conninfo(),
        max_size=CHECKPOINTER_POOL_MAX_SIZE,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    return AsyncPostgresSaver(pool)
