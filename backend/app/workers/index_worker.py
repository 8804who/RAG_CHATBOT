import asyncio
import logging

from dependencies.services import get_index_service
from schemes.events import TOPIC_CHUNKS_EMBED, ChunkEmbeddedEvent
from workers.runner import run_worker

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    """
    chunks.embed를 소비해 Qdrant에 멱등 적재하는 Index 워커.

    같은 chunk_id로 upsert하므로 at-least-once 재처리에도 중복이 쌓이지 않는다.
    문서의 모든 청크가 적재되면 상태를 INDEXED로 전환한다.
    """
    service = get_index_service()
    await run_worker(
        topic=TOPIC_CHUNKS_EMBED,
        group_id="index-workers",
        stage="indexing",
        event_type=ChunkEmbeddedEvent,
        handler=service.handle,
    )


if __name__ == "__main__":
    asyncio.run(main())
