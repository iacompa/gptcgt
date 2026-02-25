import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

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
            email, plan, credits_remaining, credits_monthly,
            spending_cap, overage_enabled, subscription_status, current_period_end
        FROM users
        WHERE workos_user_id = $1
        """,
        user_id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="User profile not found")

    return dict(row)


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
