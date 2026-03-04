import asyncpg

from api.config import settings

_pool = None


async def init_db_pool():
    global _pool
    if not _pool:
        # F26: No fallback — missing DATABASE_URL must fail loudly in production
        db_url = settings.database_url
        if not db_url:
            raise RuntimeError(
                "FATAL: DATABASE_URL not configured. Set the DATABASE_URL environment variable."
            )
        _pool = await asyncpg.create_pool(db_url, min_size=2, max_size=20)
    return _pool


async def close_db_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if not _pool:
        raise RuntimeError("Database pool has not been initialized. Ensure lifespan startup ran.")
    return _pool
