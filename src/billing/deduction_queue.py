import logging
from datetime import datetime, timedelta

from asyncpg import Pool

from src.billing.credits import CreditService

logger = logging.getLogger(__name__)
_credit_service = CreditService()


class DeductionQueue:
    """
    Manages a retry queue for failed credit deductions.
    If a deduction fails due to transient locks, it is queued here
    and processed in the background with exponential backoff.
    """

    async def enqueue(self, pool: Pool, workos_user_id: str, mode: str, reason: str, cost_credits: int) -> None:
        """Add a failed deduction to the retry queue."""
        try:
            await pool.execute(
                """
                INSERT INTO pending_deductions (workos_user_id, mode, cost_credits, last_error)
                VALUES ($1, $2, $3, $4)
                """,
                workos_user_id,
                mode,
                cost_credits,
                reason,
            )
            logger.info(f"Queued failed deduction for {workos_user_id} (mode: {mode})")
        except Exception as e:
            logger.error(f"Failed to enqueue deduction for {workos_user_id}: {e}")

    async def process_queue(self, pool: Pool) -> int:
        """Process pending deductions. Returns the number of successfully processed items."""
        processed_count = 0
        try:
            # Fetch up to 50 due deductions
            records = await pool.fetch(
                """
                SELECT id, workos_user_id, mode, cost_credits, attempts
                FROM pending_deductions
                WHERE next_retry_at <= now() AND attempts < 5
                FOR UPDATE SKIP LOCKED
                LIMIT 50
                """
            )

            for record in records:
                record_id = record["id"]
                user_id = record["workos_user_id"]
                # mode is fetched but only used for logging if needed; removing to satisfy ruff F841
                cost_credits = record["cost_credits"]
                attempts = record["attempts"]

                res = await _credit_service.deduct_fixed(pool, user_id, cost_credits)

                if res["success"]:
                    # Success -> remove from queue
                    await pool.execute("DELETE FROM pending_deductions WHERE id = $1", record_id)
                    processed_count += 1
                    logger.info(f"Successfully recovered queued deduction for {user_id}")
                else:
                    # Failure -> exponential backoff
                    next_retry = datetime.now() + timedelta(minutes=2**attempts)
                    await pool.execute(
                        """
                        UPDATE pending_deductions
                        SET attempts = attempts + 1,
                            last_error = $2,
                            next_retry_at = $3
                        WHERE id = $1
                        """,
                        record_id,
                        res.get("reason", "Unknown error"),
                        next_retry,
                    )
                    logger.warning(f"Retried deduction failed for {user_id}. Attempt {attempts + 1}.")
            return processed_count
        except Exception as e:
            logger.error(f"Error processing deduction queue: {e}")
            return processed_count


deduction_queue = DeductionQueue()
