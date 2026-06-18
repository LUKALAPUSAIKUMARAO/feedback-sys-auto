import redis.asyncio as aioredis
from redis.asyncio import Redis
from app.core.config import settings
from typing import Optional
import structlog

log = structlog.get_logger()

_redis_client: Optional[Redis] = None


async def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


async def close_redis():
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


async def acquire_submission_lock(participant_id: str, batch_id: str, ttl: int = 300) -> bool:
    """Distributed lock to prevent concurrent duplicate submissions."""
    redis = await get_redis()
    lock_key = f"submission_lock:{participant_id}:{batch_id}"
    result = await redis.set(lock_key, "1", nx=True, ex=ttl)
    return result is True


async def release_submission_lock(participant_id: str, batch_id: str):
    redis = await get_redis()
    lock_key = f"submission_lock:{participant_id}:{batch_id}"
    await redis.delete(lock_key)


async def mark_token_used(jti: str, ttl: int = 86400 * 4):
    """Invalidate a feedback token by its JWT ID."""
    redis = await get_redis()
    await redis.set(f"used_token:{jti}", "1", ex=ttl)


async def is_token_used(jti: str) -> bool:
    redis = await get_redis()
    return await redis.exists(f"used_token:{jti}") == 1


async def cache_set(key: str, value: str, ttl: int = 3600):
    redis = await get_redis()
    await redis.set(key, value, ex=ttl)


async def cache_get(key: str) -> Optional[str]:
    redis = await get_redis()
    return await redis.get(key)


async def cache_delete(key: str):
    redis = await get_redis()
    await redis.delete(key)
