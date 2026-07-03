from functools import lru_cache

from clients import KafkaProducerClient, QdrantDBClient, RedisClient


@lru_cache
def get_qdrant_client():
    return QdrantDBClient()


@lru_cache
def get_redis_client():
    return RedisClient()


@lru_cache
def get_kafka_producer() -> KafkaProducerClient:
    return KafkaProducerClient()
