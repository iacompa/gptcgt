import asyncpg

from api.config import settings

_pool = None


async def init_db_pool():
    global _pool
    if not _pool:
        # Fallback for local testing if DATABASE_URL is somehow missing but neon configs exist
        db_url = settings.database_url or "postgres://postgres:postgres@localhost:5432/gptcgt"
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
