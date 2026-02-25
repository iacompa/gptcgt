import logging
from typing import Optional

import asyncpg

from proxy.config import proxy_settings
from src.services.registry import services

logger = logging.getLogger(__name__)

# Global connection pool for the proxy application
_pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> None:
    """Initialize the asyncpg connection pool for the proxy."""
    global _pool
    try:
        url = proxy_settings.database_url
        if not url:
            url = services.neon.database_url

        if not url:
            logger.warning("DATABASE_URL is not set. Proxy database connections will fail.")
            return

        _pool = await asyncpg.create_pool(
            dsn=url,
            min_size=services.neon.pool_min,
            max_size=services.neon.pool_max,
            # Basic connection test
            command_timeout=60,
        )
        logger.info("Proxy database connection pool initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize proxy database pool: {e}")
        raise


async def close_db_pool() -> None:
    """Close the asyncpg connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Proxy database connection pool closed.")


def get_pool() -> asyncpg.Pool:
    """Retrieve the global connection pool. Raises an error if not initialized."""
    if not _pool:
        raise RuntimeError("Database pool is not initialized. Call init_db_pool first.")
    return _pool
