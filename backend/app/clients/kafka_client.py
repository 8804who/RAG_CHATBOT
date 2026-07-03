import logging

from aiokafka import AIOKafkaProducer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError

from core.config import config

logger = logging.getLogger(__name__)


class KafkaProducerClient:
    def __init__(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
            enable_idempotence=True,  # 중복 produce 방지
            acks="all",  # 모든 ISR 확인 후 성공 처리(내구성)
        )
        self._started = False

    async def start(self) -> None:
        """프로듀서 연결 시작"""
        if not self._started:
            await self._producer.start()
            self._started = True

    async def publish(self, topic: str, key: str, value: bytes) -> None:
        """
        메시지 발행

        Parameters:
            topic(str): 발행할 토픽
            key(str): 파티션 키 (문서 단위 국소성을 위해 document_id 사용)
            value(bytes): 직렬화된 메시지 본문
        """
        await self._producer.send_and_wait(topic, key=key.encode(), value=value)

    async def close(self) -> None:
        """프로듀서 정리"""
        if self._started:
            await self._producer.stop()
            self._started = False


async def ensure_topics(topics: list[str], *, num_partitions: int = 1) -> None:
    """
    필요한 토픽 멱등하게 생성

    Parameters:
        topics(list[str]): 생성할 토픽 이름 목록
        num_partitions(int): 토픽당 파티션 수(임베딩 처리량 확장 상한)
    """
    admin = AIOKafkaAdminClient(bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS)
    await admin.start()
    try:
        new_topics = [
            NewTopic(name=name, num_partitions=num_partitions, replication_factor=1)
            for name in topics
        ]
        try:
            await admin.create_topics(new_topics)
        except TopicAlreadyExistsError:
            pass
        except Exception as error:
            # 일부 토픽이 이미 존재해도 나머지 생성은 시도되므로 경고만 남긴다.
            logger.warning("kafka_client-ensure_topics-error: %s", error)
    finally:
        await admin.close()
