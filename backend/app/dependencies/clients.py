from functools import lru_cache

from langfuse.langchain import CallbackHandler

from clients import KafkaProducerClient, QdrantDBClient, RedisClient
from core.config import config


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
