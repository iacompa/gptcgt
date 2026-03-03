from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.database import get_pool
from src.billing.stripe_service import StripeService

router = APIRouter(tags=["billing"])
stripe_service = StripeService()


class CheckoutRequest(BaseModel):
    plan: str  # "pro", "team", "enterprise"
    annual: bool = False
    quantity: int = 1


class CreditPurchaseRequest(BaseModel):
    credit_amount: int  # Any amount between 100 and 50000


class CheckoutResponse(BaseModel):
    url: str


class BillingStatusResponse(BaseModel):
    plan: str
    credits_remaining: int
    credits_monthly: int
    subscription_status: str
    current_period_end: Optional[str] = None
    overage_enabled: bool
    spending_cap: Optional[int] = None
    team_role: str
    allocated_quota: Optional[int] = None
    billing_access: bool


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(request: Request, body: CheckoutRequest):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if body.plan not in ("pro", "team", "enterprise"):
        raise HTTPException(status_code=400, detail="Invalid plan")

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT email FROM users WHERE workos_user_id = $1", user_id)
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

    result = await stripe_service.create_checkout_session(
        pool, user_id, row["email"], body.plan, body.annual, body.quantity
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result.get("error"))

    return CheckoutResponse(url=result["url"])


@router.post("/credits", response_model=CheckoutResponse)
async def purchase_credits(request: Request, body: CreditPurchaseRequest):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if body.credit_amount < 100 or body.credit_amount > 50000:
        raise HTTPException(
            status_code=400, detail="Credit amount must be between 100 and 50000."
        )

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT email FROM users WHERE workos_user_id = $1", user_id)
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

    price_cents = body.credit_amount * 4  # $0.04 per credit
    result = await stripe_service.create_credit_purchase_session(
        pool, user_id, body.credit_amount, price_cents
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result.get("error"))

    return CheckoutResponse(url=result["url"])


@router.post("/portal", response_model=CheckoutResponse)
async def create_portal(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT stripe_customer_id FROM users WHERE workos_user_id = $1", user_id
        )
        if not row or not row["stripe_customer_id"]:
            raise HTTPException(status_code=400, detail="User has no Stripe customer ID")

    result = await stripe_service.create_customer_portal(pool, user_id)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result.get("error"))

    return CheckoutResponse(url=result["url"])


@router.get("/status", response_model=BillingStatusResponse)
async def get_status(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT u.plan, u.credits_remaining, u.credits_monthly,
               u.subscription_status, u.current_period_end, u.overage_enabled, u.spending_cap,
               u.team_role, u.allocated_quota, u.billing_access, t.shared_credits_remaining
               FROM users u
               LEFT JOIN teams t ON u.team_id = t.id
               WHERE u.workos_user_id = $1""",
            user_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

    period_end = None
    if row["current_period_end"]:
        period_end = row["current_period_end"].isoformat()

    # Use team wallet balance if available, fall back to personal credits
    effective_credits = row["shared_credits_remaining"] if row["shared_credits_remaining"] is not None else (row["credits_remaining"] or 0)

    return BillingStatusResponse(
        plan=row["plan"] or "free",
        credits_remaining=effective_credits,
        credits_monthly=row["credits_monthly"] or 0,
        subscription_status=row["subscription_status"] or "none",
        current_period_end=period_end,
        overage_enabled=row["overage_enabled"] or False,
        spending_cap=row["spending_cap"],
        team_role=row["team_role"] or "owner",
        allocated_quota=row["allocated_quota"],
        billing_access=row["billing_access"] if row["billing_access"] is not None else True
    )


@router.post("/webhook")
async def handle_stripe_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    db_pool = get_pool()
    result = await stripe_service.handle_webhook(db_pool, payload, signature)

    if result.get("status") in ["invalid_payload", "invalid_signature"]:
        raise HTTPException(status_code=400, detail=result.get("error"))

    return {"status": "ok"}
