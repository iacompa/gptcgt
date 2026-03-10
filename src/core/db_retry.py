import asyncio
import logging
from functools import wraps
from typing import Any, Callable

import asyncpg

logger = logging.getLogger(__name__)


def with_db_retry(max_retries: int = 3, base_delay: float = 0.5) -> Callable:
    """
    Decorator to retry async database operations upon transient failures.
    Catches specific asyncpg exceptions (e.g., deadlock, connection drop).
    Uses exponential backoff with jitter.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            retries = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except (
                    asyncpg.exceptions.DeadlockDetectedError,
                    asyncpg.exceptions.SerializationFailureError,
                    asyncpg.exceptions.ConnectionDoesNotExistError,
                    asyncpg.exceptions.CannotConnectNowError,
                    asyncpg.exceptions.TooManyConnectionsError,
                    asyncpg.exceptions.AdminShutdownError,
                ) as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"DB operation '{func.__name__}' failed after {max_retries} retries: {e}")
                        raise

                    delay = base_delay * (2 ** (retries - 1))
                    # Add simple jitter (up to 20%)
                    import random

                    jitter = delay * 0.2 * random.random()
                    total_delay = delay + jitter

                    logger.warning(
                        f"Transient DB error in '{func.__name__}': {type(e).__name__} - {e}. "
                        f"Retrying in {total_delay:.2f}s (Attempt {retries}/{max_retries})"
                    )
                    await asyncio.sleep(total_delay)
                except asyncpg.PostgresError as e:
                    # Generic Postgres errors should not be retried blind
                    logger.error(f"Non-retriable Postgres error in '{func.__name__}': {e}")
                    raise

        return wrapper

    return decorator
