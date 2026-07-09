import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import TypeVar

from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import AsyncSession

from clients import ensure_topics
from core.config import config
from dependencies.clients import get_kafka_producer
from dependencies.repositories import get_document_status_repository, get_log_repository
from dependencies.db import AsyncSessionLocal
from models import DocumentOperation
from schemes.events import ALL_TOPICS, TOPIC_DOCUMENTS_DLQ, DlqEvent

logger = logging.getLogger(__name__)

TEvent = TypeVar("TEvent")


async def run_worker(
    *,
    topic: str,
    group_id: str,
    stage: str,
    event_type: type[TEvent],
    handler: Callable[[AsyncSession, TEvent], Awaitable[None]],
) -> None:
    """
    한 단계 컨슈머 루프(파서/임베드/인덱스 공통).

    at-least-once로 소비한다: 메시지를 처리(내부 N회 재시도)한 뒤에만 offset을 커밋한다.
    최종 실패한 메시지는 documents.dlq로 격리하고 문서를 FAILED로 표시한 다음 offset을
    전진시켜, 포이즌 메시지가 파티션을 영원히 막지 않게 한다(RAG_ARCHITECTURE §5.4).

    Parameters:
        topic(str): 소비할 토픽
        group_id(str): 컨슈머 그룹 id(단계별로 분리 → 독립 스케일)
        stage(str): 단계 이름(로그·DLQ 표기용)
        event_type(type): 메시지를 역직렬화할 이벤트 클래스
        handler(Callable): (db, event)를 받아 처리하는 코루틴
    """
    await ensure_topics(ALL_TOPICS)
    producer = get_kafka_producer()
    await producer.start()
    status_repository = get_document_status_repository()
    log_repository = get_log_repository()

    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        group_id=group_id,
        enable_auto_commit=False,  # 처리 성공 후 수동 커밋(at-least-once)
        auto_offset_reset="earliest",
    )
    await consumer.start()
    logger.info("worker started: stage=%s, topic=%s, group=%s", stage, topic, group_id)
    try:
        async for message in consumer:
            await _process_message(
                message,
                stage=stage,
                event_type=event_type,
                handler=handler,
                status_repository=status_repository,
                log_repository=log_repository,
            )
            await consumer.commit()
    finally:
        await consumer.stop()
        await producer.close()


async def _process_message(
    message,
    *,
    stage: str,
    event_type: type[TEvent],
    handler: Callable[[AsyncSession, TEvent], Awaitable[None]],
    status_repository,
    log_repository,
) -> None:
    """단일 메시지 처리: 역직렬화 → 재시도 → 성공/최종 실패(DLQ) 처리."""
    key = message.key.decode() if message.key else None

    try:
        event = event_type.from_bytes(message.value)
    except Exception as error:
        # 역직렬화 불가한 포이즌 메시지는 재시도 없이 바로 DLQ로 격리.
        logger.exception("worker-%s-decode-error", stage)
        await _send_to_dlq(
            stage=stage,
            error=str(error),
            retry_count=0,
            source_topic=message.topic,
            key=key,
            raw=message.value,
        )
        return

    document_id = getattr(event, "document_id", None)
    last_error: Exception | None = None
    for attempt in range(1, config.INGEST_MAX_RETRIES + 1):
        try:
            async with AsyncSessionLocal() as db:
                await handler(db, event)
            return
        except Exception as error:
            last_error = error
            logger.warning(
                "worker-%s-attempt-failed: attempt=%d/%d, document_id=%s, error=%s",
                stage,
                attempt,
                config.INGEST_MAX_RETRIES,
                document_id,
                error,
            )
            if attempt < config.INGEST_MAX_RETRIES:
                await asyncio.sleep(0.5 * 2 ** (attempt - 1))

    # 재시도 소진 → 문서 FAILED 표시 + DLQ 격리.
    logger.error("worker-%s-error: document_id=%s 최종 실패 → DLQ", stage, document_id)
    if document_id is not None:
        try:
            async with AsyncSessionLocal() as db:
                await status_repository.set_failed(db, document_id, str(last_error))
        except Exception:
            logger.exception("worker-%s-set_failed-error", stage)
        await _log_ingest_failure(
            stage=stage,
            document_id=document_id,
            event=event,
            error=str(last_error),
            status_repository=status_repository,
            log_repository=log_repository,
        )
    await _send_to_dlq(
        stage=stage,
        error=str(last_error),
        retry_count=config.INGEST_MAX_RETRIES,
        source_topic=message.topic,
        key=key,
        raw=message.value,
    )


async def _log_ingest_failure(
    *,
    stage: str,
    document_id: str,
    event: object,
    error: str,
    status_repository,
    log_repository,
) -> None:
    """단계 무관 최종 실패를 문서 관리 이력에 기록(성공 로그와 대칭).

    delete_document는 성공·실패를 모두 기록하는데, 인제스트 파이프라인은 성공
    로그(IndexService)만 있고 실패는 기록되지 않아 감사 이력에 빠지는 케이스가
    있었다. 어느 단계(parser/embed/index)에서 최종 실패해도 여기서 한 곳에 기록한다.
    """
    try:
        async with AsyncSessionLocal() as db:
            record = await status_repository.get(db, document_id)
            started_at = record.created_at if record else datetime.now(timezone.utc)
            await log_repository.create_document_manage_log(
                db,
                operation=DocumentOperation.INSERT,
                collection_name=getattr(event, "collection_name", ""),
                filename=getattr(event, "filename", None),
                requester_id=getattr(event, "requester_id", None),
                requester_email=getattr(event, "requester_email", None),
                status="failed",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                document_id=document_id,
            )
    except Exception:
        logger.exception("worker-%s-log-failure-error", stage)


async def _send_to_dlq(
    *,
    stage: str,
    error: str,
    retry_count: int,
    source_topic: str,
    key: str | None,
    raw: bytes,
) -> None:
    """실패한 원본 메시지를 documents.dlq로 발행."""
    dlq_event = DlqEvent(
        stage=stage,
        error=error,
        retry_count=retry_count,
        source_topic=source_topic,
        key=key,
        original=raw.decode(errors="replace"),
    )
    await get_kafka_producer().publish(
        TOPIC_DOCUMENTS_DLQ, key=key or stage, value=dlq_event.to_bytes()
    )
