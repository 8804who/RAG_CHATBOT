import asyncio
import logging

from dependencies.services import get_parser_service
from schemes.events import TOPIC_DOCUMENTS_UPLOADED, DocumentUploadedEvent
from workers.runner import run_worker

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    """
    documents.uploaded를 소비해 청킹 후 documents.parsed로 발행하는 Parser 워커.

    consumer group 'parser-workers'로 묶여 파티션을 나눠 가지므로, 프로세스를
    늘리면 파싱 처리량이 수평 확장된다.
    """
    service = get_parser_service()
    await run_worker(
        topic=TOPIC_DOCUMENTS_UPLOADED,
        group_id="parser-workers",
        stage="parsing",
        event_type=DocumentUploadedEvent,
        handler=service.handle,
    )


if __name__ == "__main__":
    asyncio.run(main())
