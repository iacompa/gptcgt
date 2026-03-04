# ruff: noqa: E501

import logging
from datetime import datetime

from proxy.database import get_pool
from src.billing.credits import CreditService

logger = logging.getLogger(__name__)

_credit_service = CreditService()


class UsageMeter:
    def __init__(self, mode: str, workos_user_id: str, cost_credits: int):
        self.mode = mode
        self.workos_user_id = workos_user_id
        self.cost_credits = cost_credits
        self.input_tokens = 0
        self.output_tokens = 0
        self.models_used = set()
        self.start_time = datetime.now()
        self._finalized = False

    async def stream_and_meter(self, litellm_response):
        """Yields chunks while counting tokens."""
        try:
            async for chunk in litellm_response:
                # Safely extract token counts if LiteLLM provides them in the stream
                if hasattr(chunk, "usage") and chunk.usage:
                    self.input_tokens = getattr(chunk.usage, "prompt_tokens", self.input_tokens)
                    self.output_tokens = getattr(
                        chunk.usage, "completion_tokens", self.output_tokens
                    )

                if hasattr(chunk, "model") and chunk.model:
                    self.models_used.add(chunk.model)

                yield chunk.model_dump_json() + "\n"
        finally:
            # Finalize ensures usage is updated even if client disconnects early
            await self._finalize_usage()

    async def finalize_non_stream(self, response):
        """Finalize usage for non-streaming response."""
        if hasattr(response, "usage") and response.usage:
            self.input_tokens = getattr(response.usage, "prompt_tokens", 0)
            self.output_tokens = getattr(response.usage, "completion_tokens", 0)

        if hasattr(response, "model") and response.model:
            self.models_used.add(response.model)

        await self._finalize_usage()

    async def _finalize_usage(self):
        """Deduct credits and log usage event in the background."""
        if self._finalized:
            return
        self._finalized = True
        try:
            pool = get_pool()

            # Look up internal UUID
            internal_id = await pool.fetchval(
                "SELECT id FROM users WHERE workos_user_id = $1", self.workos_user_id
            )

            if not internal_id:
                logger.error(
                    f"Cannot finalize usage: User UUID not found for workos_id {self.workos_user_id}"  # noqa: E501
                )
                return

            # Deduct credits via the unified CreditService (row-level FOR UPDATE lock)
            deduction = await _credit_service.deduct(pool, self.workos_user_id, self.mode)

            if not deduction["success"]:
                logger.error(
                    f"Usage metered but deduction failed for {self.workos_user_id}: {deduction.get('reason')}"
                )

            models_array = list(self.models_used) if self.models_used else ["unknown"]

            # Calculate duration
            duration_ms = int((datetime.now() - self.start_time).total_seconds() * 1000)

            # Log exact usage event
            await pool.execute(
                """
                INSERT INTO usage_events
                (user_id, task_mode, credits_consumed, models_used, input_tokens, output_tokens, success, duration_ms, created_at)  # noqa: E501
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now())
                """,
                internal_id,
                self.mode,
                self.cost_credits,
                models_array,
                self.input_tokens,
                self.output_tokens,
                True,
                duration_ms,
            )

            logger.info(
                f"Usage finalized: {self.workos_user_id} | {self.mode} | {self.cost_credits}cr | {len(models_array)} models"  # noqa: E501
            )
        except Exception as e:
            logger.error(f"Failed to finalize usage and deduct credits: {e}")

    async def record_fixed_cost(self, event_type: str = "sandbox_run"):
        """Deduct a fixed cost without stream tracking (e.g. for E2B sandbox runs)."""
        if self._finalized:
            return
        self._finalized = True
        try:
            pool = get_pool()
            internal_id = await pool.fetchval(
                "SELECT id FROM users WHERE workos_user_id = $1", self.workos_user_id
            )
            if not internal_id:
                logger.error(f"Cannot record fixed cost: User UUID not found for workos_id {self.workos_user_id}")
                return

            deduction = await _credit_service.deduct(pool, self.workos_user_id, self.mode)
            if not deduction["success"]:
                logger.error(f"Fixed cost deduction failed for {self.workos_user_id}: {deduction.get('reason')}")

            duration_ms = int((datetime.now() - self.start_time).total_seconds() * 1000)
            await pool.execute(
                """
                INSERT INTO usage_events
                (user_id, task_mode, credits_consumed, models_used, input_tokens, output_tokens, success, duration_ms, created_at)
                VALUES ($1, $2, $3, $4, 0, 0, true, $5, now())
                """,
                internal_id,
                self.mode,
                self.cost_credits,
                [event_type],
                duration_ms,
            )
            logger.info(f"Fixed usage finalized: {self.workos_user_id} | {self.cost_credits}cr for {event_type}")
        except Exception as e:
            logger.error(f"Failed to record fixed cost: {e}")
