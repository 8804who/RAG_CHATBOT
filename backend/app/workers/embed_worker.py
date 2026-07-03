import asyncio
import logging

from dependencies.services import get_embed_ingest_service
from schemes.events import TOPIC_DOCUMENTS_PARSED, DocumentParsedEvent
from workers.runner import run_worker

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    """
    documents.parsed를 소비해 임베딩 후 chunks.embed로 발행하는 Embed 워커.

    consumer group 'embed-workers'로 묶여 파티션을 나눠 가지므로, 프로세스를
    늘리면 임베딩 처리량이 수평 확장된다(임베딩 API rate limit은 pull 속도로 흡수).
    """
    service = get_embed_ingest_service()
    await run_worker(
        topic=TOPIC_DOCUMENTS_PARSED,
        group_id="embed-workers",
        stage="embedding",
        event_type=DocumentParsedEvent,
        handler=service.handle,
    )


if __name__ == "__main__":
    asyncio.run(main())
