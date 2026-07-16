import asyncio
import logging

from dependencies.clients import get_kafka_producer
from dependencies.services import (
    get_embed_ingest_service,
    get_index_service,
    get_parser_service,
)
from schemes.events import (
    TOPIC_CHUNKS_EMBED,
    TOPIC_DOCUMENTS_PARSED,
    TOPIC_DOCUMENTS_UPLOADED,
    ChunkEmbeddedEvent,
    DocumentParsedEvent,
    DocumentUploadedEvent,
)
from workers.runner import run_worker

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    """
    임베딩 작업 수행 파서
    """
    producer = get_kafka_producer()
    await producer.start()
    try:
        await asyncio.gather(
            run_worker(
                topic=TOPIC_DOCUMENTS_UPLOADED,
                group_id="parser-workers",
                stage="parsing",
                event_type=DocumentUploadedEvent,
                handler=get_parser_service().handle,
                manage_producer=False,
            ),
            run_worker(
                topic=TOPIC_DOCUMENTS_PARSED,
                group_id="embed-workers",
                stage="embedding",
                event_type=DocumentParsedEvent,
                handler=get_embed_ingest_service().handle,
                manage_producer=False,
            ),
            run_worker(
                topic=TOPIC_CHUNKS_EMBED,
                group_id="index-workers",
                stage="indexing",
                event_type=ChunkEmbeddedEvent,
                handler=get_index_service().handle,
                manage_producer=False,
            ),
        )
    finally:
        await producer.close()


if __name__ == "__main__":
    asyncio.run(main())
