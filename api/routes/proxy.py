"""
Proxy Usage Recording & Credit Deduction

This endpoint is called by the CLI tool AFTER every successful AI API call.
It performs three atomic operations:
1. Deducts credits from the team wallet
2. Writes an immutable usage_log row for audit/tax/dispute resolution
3. Returns the remaining balance so the CLI can display it
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.database import get_pool

logger = logging.getLogger(__name__)
router = APIRouter(tags=["proxy"])


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
    """Record AI usage, deduct from team wallet, write immutable audit log."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = get_pool()
    async with pool.acquire() as conn:
        # Fetch the user's team info
        user_row = await conn.fetchrow(
            """
            SELECT u.id as user_internal_id, u.team_id, u.allocated_quota,
                   t.shared_credits_remaining
            FROM users u
            LEFT JOIN teams t ON u.team_id = t.id
            WHERE u.workos_user_id = $1
            """,
            user_id,
        )

        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")

        team_id = user_row["team_id"]
        current_credits = user_row["shared_credits_remaining"] or 0

        # Check if credits are exhausted BEFORE deducting
        if current_credits <= 0:
            return RecordUsageResponse(
                credits_remaining=0,
                credits_exhausted=True,
                message="⚠️ Credits exhausted. Visit https://gptcgt.ai/dashboard/billing to purchase more.",
            )

        # Check individual quota if set
        quota = user_row["allocated_quota"]
        if quota is not None and quota <= 0:
            return RecordUsageResponse(
                credits_remaining=current_credits,
                credits_exhausted=True,
                message="⚠️ Your personal quota is exhausted. Ask your Team Admin for more credits.",
            )

        # Atomic: deduct 1 credit from team wallet
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE teams
                SET shared_credits_remaining = GREATEST(shared_credits_remaining - 1, 0)
                WHERE id = $1
                """,
                team_id,
            )

            # Deduct from individual quota if applicable
            if quota is not None:
                await conn.execute(
                    """
                    UPDATE users
                    SET allocated_quota = GREATEST(allocated_quota - 1, 0)
                    WHERE workos_user_id = $1
                    """,
                    user_id,
                )

            # Write immutable usage log
            await conn.execute(
                """
                INSERT INTO usage_logs (team_id, user_id, action, tokens_used)
                VALUES ($1, $2, $3, $4)
                """,
                team_id,
                user_row["user_internal_id"],
                f"{body.action} ({body.model or 'unknown'})",
                body.tokens_used,
            )

        new_balance = max(current_credits - 1, 0)
        return RecordUsageResponse(
            credits_remaining=new_balance,
            credits_exhausted=new_balance <= 0,
            message=f"Usage recorded. {new_balance} credits remaining.",
        )
