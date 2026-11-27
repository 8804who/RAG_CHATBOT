import redis.asyncio as redis

from core.config import config


class RedisClient:
    def __init__(self):
        self.client = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            password=config.REDIS_PASSWORD or None,
            decode_responses=True,
        )

    async def get(self, key: str):
        return await self.client.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        await self.client.set(key, value, ex=ex)

    async def set_if_absent(self, key: str, value: str, ex: int) -> bool:
        """
        키가 없을 때만 TTL과 함께 저장(SET NX EX, 분산 잠금용)

        Parameters:
            key(str): 키
            value(str): 값
            ex(int): 만료 시간(초)

        Returns:
            bool: 저장했으면 True, 이미 있으면 False
        """
        return bool(await self.client.set(key, value, nx=True, ex=ex))

    async def delete(self, key: str) -> None:
        """
        키 삭제

        Parameters:
            key(str): 삭제할 키
        """
        await self.client.delete(key)

    async def close(self):
        await self.client.close()
