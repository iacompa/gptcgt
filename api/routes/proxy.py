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
from src.billing.credits import CreditService, resolve_billing_mode
from src.billing.spending_caps import SpendingCapService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["proxy"])
credit_service = CreditService()
spending_caps = SpendingCapService()


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
    mode = resolve_billing_mode(body.model)

    cost = credit_service.CREDIT_COSTS.get(mode, 5)

    # F08: Spending cap enforcement (was missing — bypass path vs main proxy)
    cap_status = await spending_caps.check_before_task(pool, user_id, cost)
    if not cap_status["allowed"]:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Spending cap exceeded: ${cap_status.get('spent_dollars', 0):.2f} spent "
                f"of ${cap_status.get('cap_dollars', 0)} cap"
            ),
        )

    deduction = await credit_service.check_and_deduct(pool, user_id, mode)
    if not deduction["can_proceed"]:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Insufficient credits. Requires {deduction.get('credits_cost', cost)}. "
                f"Remaining: {deduction.get('remaining', 0)}"
            ),
        )

    async with pool.acquire() as conn:
        user_row = await conn.fetchrow(
            "SELECT id, team_id FROM users WHERE workos_user_id = $1",
            user_id,
        )
        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")

        await conn.execute(
            """
            INSERT INTO usage_events
            (
                user_id, team_id, task_mode, credits_consumed, models_used,
                input_tokens, output_tokens, success, duration_ms, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, 0, true, 0, now())
            """,
            user_row["id"],
            user_row["team_id"],
            mode,
            cost,
            [body.model or "unknown"],
            max(body.tokens_used, 0),
        )

    new_balance = deduction.get("new_balance", 0)
    return RecordUsageResponse(
        credits_remaining=new_balance,
        credits_exhausted=new_balance <= 0,
        message=f"Usage recorded. {new_balance} credits remaining.",
    )
