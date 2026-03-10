import asyncio
import logging

from api.database import get_pool
from src.billing.deduction_queue import deduction_queue

logger = logging.getLogger(__name__)

async def process_deductions_loop():
    """Background worker to process the pending_deductions queue."""
    logger.info("Starting deduction_worker loop...")
    while True:
        try:
            pool = get_pool()
            if pool:
                processed = await deduction_queue.process_queue(pool)
                if processed > 0:
                    logger.info(f"deduction_worker: Processed {processed} items.")
        except Exception as e:
            logger.error(f"Error in deduction_worker: {e}")
        await asyncio.sleep(60)
