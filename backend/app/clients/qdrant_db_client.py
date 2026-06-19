from qdrant_client import AsyncQdrantClient

from core.config import config


class QdrantDBClient:
    def __init__(self):
        self.client = AsyncQdrantClient(
            url=config.QDRANT_URL,
            api_key=config.QDRANT_API_KEY,
        )

    async def close(self) -> None:
        await self.client.close()
