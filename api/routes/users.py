import logging
import uuid
from typing import Optional

import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.config import settings
from api.database import get_pool
from src.billing.spending_caps import SpendingCapService

logger = logging.getLogger(__name__)
# Changed from "users" back to "user" so the endpoint becomes /user/me
router = APIRouter(tags=["users"])

spending_caps = SpendingCapService()


class CapUpdateRequest(BaseModel):
    spending_cap: Optional[int]


@router.get("/me")
async def get_current_user_profile(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT
            u.email, u.plan, u.credits_remaining, u.credits_monthly,
            u.spending_cap, u.overage_enabled, u.subscription_status, u.current_period_end,
            u.team_role, u.allocated_quota, u.billing_access,
            COALESCE(t.shared_credits_remaining, u.credits_remaining, 0) as team_credits_remaining
        FROM users u
        LEFT JOIN teams t ON u.team_id = t.id
        WHERE u.workos_user_id = $1
        """,
        user_id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="User profile not found")

    result = dict(row)
    # Use team wallet as the primary credits display
    result["credits_remaining"] = result.pop("team_credits_remaining", result.get("credits_remaining", 0))
    return result


class ProfileUpdateRequest(BaseModel):
    tos_version: Optional[str] = None


@router.patch("/me")
async def update_profile(update: ProfileUpdateRequest, request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    pool = get_pool()
    resp = {"status": "success"}

    if update.tos_version is not None:
        await pool.execute(
            "UPDATE users SET tos_version = $1, tos_accepted_at = now() WHERE workos_user_id = $2",
            update.tos_version,
            user_id,
        )
        resp["tos_version"] = update.tos_version

    return resp


@router.patch("/me/spending_cap")
async def update_spending_cap(update: CapUpdateRequest, request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    pool = get_pool()
    if update.spending_cap is None:
        await spending_caps.remove_cap(pool, user_id)
    else:
        if update.spending_cap < 0:
            raise HTTPException(status_code=400, detail="Cap cannot be negative")
        await spending_caps.set_cap(pool, user_id, update.spending_cap)
    return {"status": "success", "cap": update.spending_cap}


@router.delete("/me")
async def delete_account(request: Request):
    """
    P2-02: User-initiated Account Deletion.

    Hard deletes the Auth mapping (workos_user_id) to immediately prevent
    any future sign-ins, and scrambles the email to an anonymized UUID to
    preserve referential integrity on past billing/usage records without
    holding PII.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    pool = get_pool()

    # 1. Look up the native DB ID, email, and Stripe subscription
    row = await pool.fetchrow("SELECT id, email FROM users WHERE workos_user_id = $1", user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")

    native_id = row["id"]
    old_email = row["email"]
    stripe_sub_id = None
    if hasattr(pool, "fetchval"):
        stripe_sub_id = await pool.fetchval(
            "SELECT stripe_subscription_id FROM users WHERE id = $1",
            native_id,
        )
    elif isinstance(row, dict):
        stripe_sub_id = row.get("stripe_subscription_id")

    if stripe_sub_id:
        try:
            stripe.api_key = settings.stripe_secret_key
            stripe.Subscription.delete(stripe_sub_id)
        except Exception as e:
            logger.error(f"Failed to cancel Stripe subscription {stripe_sub_id} during account deletion: {e}")

    # Scramble PII but keep the physical record for FK constraints
    scrambled_email = f"deleted_{uuid.uuid4().hex}@gptcgt.ai"

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Disconnect API keys using the canonical native UUID
            await conn.execute("UPDATE api_keys SET is_active = false WHERE owner_id = $1 AND owner_type = 'user'", native_id)

            # Anonymize User
            await conn.execute(
                """
                UPDATE users
                SET email = $1,
                    password_hash = NULL,
                    workos_user_id = $2,
                    subscription_status = 'cancelled',
                    plan = 'free',
                    credits_remaining = 0,
                    credits_monthly = 0
                WHERE id = $3
                """,
                scrambled_email,
                f"deleted_{native_id}",
                native_id,
            )

    logger.info(f"Account for {old_email} (ID: {native_id}) successfully anonymized/deleted.")
    return {"status": "success", "message": "Account securely deleted"}
