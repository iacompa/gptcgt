import asyncio
import hashlib
import json
import logging
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Lightweight caching layer for high-frequency queries.
    Uses Redis if REDIS_URL is configured in ServiceRegistry,
    otherwise degrades gracefully to an in-memory TTL cache.
    """

    def __init__(self):
        self._memory_cache = {}
        self._redis = None
        self._initialized = False

    async def _init_redis(self):
        if self._initialized:
            return
        self._initialized = True
        try:
            from src.services.registry import services

            if services.redis.is_configured:
                import redis.asyncio as redis_async

                self._redis = redis_async.from_url(services.redis.url, decode_responses=True)
                logger.info("Redis cache initialized.")
            else:
                logger.info("Redis not configured. Falling back to in-memory cache.")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis: {e}. Using memory fallback.")

    async def get(self, key: str) -> Any:
        await self._init_redis()
        if self._redis:
            try:
                val = await self._redis.get(key)
                return json.loads(val) if val else None
            except Exception:
                pass

        # Memory fallback
        if key in self._memory_cache:
            val, expires_at = self._memory_cache[key]
            if asyncio.get_event_loop().time() < expires_at:
                return val
            else:
                del self._memory_cache[key]
        return None

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        await self._init_redis()
        if self._redis:
            try:
                await self._redis.setex(key, ttl, json.dumps(value))
                return
            except Exception:
                pass

        # Memory fallback
        self._memory_cache[key] = (value, asyncio.get_event_loop().time() + ttl)


cache_manager = CacheManager()


def cached(ttl: int = 60):
    """Cache the result of an async function based on its arguments."""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate a cache key from module, function, and arguments
            key_data = f"{func.__module__}:{func.__name__}:{args}:{kwargs}"
            key_hash = hashlib.sha256(key_data.encode()).hexdigest()
            cache_key = f"cache:{key_hash}"

            cached_val = await cache_manager.get(cache_key)
            if cached_val is not None:
                return cached_val

            val = await func(*args, **kwargs)

            # Can only cache Pydantic models or JSON serializable dicts
            cache_val = val.model_dump() if hasattr(val, "model_dump") else val
            await cache_manager.set(cache_key, cache_val, ttl)
            return val

        return wrapper

    return decorator
