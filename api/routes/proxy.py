"""
Proxy usage recording for legacy clients.

This endpoint mirrors the same credit mode logic used by the LiteLLM proxy:
- Determine mode from model server-side
- Check credits
- Deduct credits atomically
- Write immutable usage_events row
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.database import get_pool
from api.services.cost_computation import determine_tier
from src.billing.credits import CreditService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["proxy"])
credit_service = CreditService()


class RecordUsageRequest(BaseModel):
    action: str  # e.g. "chat_completion", "code_generation"
    tokens_used: int
    model: Optional[str] = None


class RecordUsageResponse(BaseModel):
    credits_remaining: int
    credits_exhausted: bool
    message: str


@router.post("/record_usage", response_model=RecordUsageResponse)
async def record_usage(request: Request, body: RecordUsageRequest):
    """Record usage and deduct credits with the shared mode-based billing policy."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = get_pool()
    mode = determine_tier(body.model or "")

    affordability = await credit_service.check_credits(pool, user_id, mode)
    if not affordability["can_proceed"]:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Insufficient credits. Requires {affordability['credits_cost']}. "
                f"Remaining: {affordability['remaining']}"
            ),
        )

    deduction = await credit_service.deduct(pool, user_id, mode)
    if not deduction.get("success"):
        raise HTTPException(status_code=402, detail="Insufficient credits")

    async with pool.acquire() as conn:
        internal_id = await conn.fetchval(
            "SELECT id FROM users WHERE workos_user_id = $1",
            user_id,
        )
        if not internal_id:
            raise HTTPException(status_code=404, detail="User not found")

        await conn.execute(
            """
            INSERT INTO usage_events
            (
                user_id, task_mode, credits_consumed, models_used,
                input_tokens, output_tokens, success, duration_ms, created_at
            )
            VALUES ($1, $2, $3, $4, $5, 0, true, 0, now())
            """,
            internal_id,
            mode,
            affordability["credits_cost"],
            [body.model or "unknown"],
            max(body.tokens_used, 0),
        )

    new_balance = deduction.get("new_balance", 0)
    return RecordUsageResponse(
        credits_remaining=new_balance,
        credits_exhausted=new_balance <= 0,
        message=f"Usage recorded. {new_balance} credits remaining.",
    )
