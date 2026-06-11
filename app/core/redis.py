import redis.asyncio as redis
from app.core.config import get_settings

settings = get_settings()

class RedisClient:
    def __init__(self):
        self.redis_url = str(settings.REDIS_URL)
        self._client: redis.Redis | None = None

    async def get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None

redis_client = RedisClient()

async def get_redis():
    client = await redis_client.get_client()
    try:
        yield client
    finally:
        # We don't close here as it's a singleton-like client for the app lifecycle
        pass
