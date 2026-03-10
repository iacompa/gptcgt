import re
from typing import Optional

from src.core.db_retry import with_db_retry


def resolve_billing_mode(model: Optional[str]) -> str:
    """
    Determine billing mode from the model name (server-side).
    Prevents billing fraud via client-controlled headers.
    """
    if not model:
        return "standard"
    model_lower = model.lower()

    # Scout-tier: small/cheap models
    scout_keywords = ("haiku", "flash", "nano", "small", "lite")
    if any(kw in model_lower for kw in scout_keywords):
        return "scout"

    # Special exact match for "mini" (like o3-mini, gpt-4o-mini) to avoid flagging "gemini" as scout
    if re.search(r"\bmini\b", model_lower):
        return "scout"

    # Architect-tier: reasoning/o-series models
    if re.search(r"\b(o1|o3|o3-pro|reasoning|opus)\b", model_lower):
        return "architect"

    # Ensemble-tier: multiple models or ensemble markers
    if "ensemble" in model_lower:
        return "ensemble"

    return "standard"


class CreditService:
    @property
    def CREDIT_COSTS(self):
        from api.config import settings
        return {
            "scout": settings.credit_cost_scout,
            "standard": settings.credit_cost_standard,
            "ensemble": settings.credit_cost_ensemble,
            "architect": settings.credit_cost_architect,
            "battle": settings.credit_cost_battle,
            "sandbox": settings.credit_cost_sandbox,
        }

    @with_db_retry()
    async def check_credits(self, db_pool, workos_user_id: str, mode: str) -> dict:
        """Pre-task check: can user afford this mode? Checks team wallet if applicable."""
        cost = self.CREDIT_COSTS.get(mode, 5)
        row = await db_pool.fetchrow(
            """
            SELECT u.id, u.plan, u.allocated_quota, u.team_id,
                   COALESCE(t.overage_enabled, u.overage_enabled) as overage_enabled,
                   COALESCE(t.shared_credits_remaining, u.credits_remaining, 0) as effective_credits
            FROM users u
            LEFT JOIN teams t ON u.team_id = t.id
            WHERE u.workos_user_id = $1
            """,
            workos_user_id,
        )
        if not row:
            return {"can_proceed": False, "action": "block", "credits_cost": cost, "remaining": 0}

        remaining = row["effective_credits"]
        overage = row["overage_enabled"]

        if remaining >= cost:
            return {
                "can_proceed": True,
                "action": "proceed",
                "credits_cost": cost,
                "remaining": remaining,
            }
        if overage:
            return {
                "can_proceed": True,
                "action": "proceed_overage",
                "credits_cost": cost,
                "remaining": remaining,
            }
        if remaining > 0:
            # Suggest cheaper mode
            affordable = self.find_affordable_mode(remaining)
            return {
                "can_proceed": False,
                "action": "suggest_downgrade",
                "credits_cost": cost,
                "remaining": remaining,
                "suggested_mode": affordable,
            }
        return {"can_proceed": False, "action": "block", "credits_cost": cost, "remaining": 0}

    @with_db_retry()
    async def check_and_deduct(self, db_pool, workos_user_id: str, mode: str) -> dict:
        """Atomic check and deduct to prevent race conditions."""
        cost = self.CREDIT_COSTS.get(mode, 5)

        async with db_pool.acquire() as conn:
            async with conn.transaction():
                user_row = await conn.fetchrow(
                    "SELECT id, team_id, credits_remaining, overage_enabled "
                    "FROM users WHERE workos_user_id = $1 FOR UPDATE",
                    workos_user_id,
                )
                if not user_row:
                    return {"can_proceed": False, "action": "block", "credits_cost": cost, "remaining": 0, "success": False, "reason": "user_not_found"}

                overage = user_row["overage_enabled"]

                if user_row["team_id"]:
                    team_row = await conn.fetchrow(
                        "SELECT id, shared_credits_remaining, overage_enabled FROM teams WHERE id = $1 FOR UPDATE",
                        user_row["team_id"],
                    )
                    if not team_row:
                        return {"can_proceed": False, "action": "block", "credits_cost": cost, "remaining": 0, "success": False, "reason": "team_not_found"}

                    team_overage = team_row["overage_enabled"] if team_row["overage_enabled"] is not None else overage
                    remaining = team_row["shared_credits_remaining"]

                    if remaining >= cost:
                        can_proceed, action = True, "proceed"
                    elif team_overage:
                        can_proceed, action = True, "proceed_overage"
                    else:
                        can_proceed = False

                    if can_proceed:
                        new_balance = remaining - cost
                        await conn.execute(
                            "UPDATE teams SET shared_credits_remaining = $1 WHERE id = $2", new_balance, team_row["id"]
                        )
                        return {"can_proceed": True, "action": action, "credits_cost": cost, "remaining": new_balance, "success": True, "new_balance": new_balance, "deducted": cost}
                    else:
                        if remaining > 0:
                            return {"can_proceed": False, "action": "suggest_downgrade", "credits_cost": cost, "remaining": remaining, "suggested_mode": self.find_affordable_mode(remaining), "success": False, "reason": "insufficient_team_credits"}
                        return {"can_proceed": False, "action": "block", "credits_cost": cost, "remaining": remaining, "success": False, "reason": "insufficient_team_credits"}
                else:
                    remaining = user_row["credits_remaining"]
                    if remaining >= cost:
                        can_proceed, action = True, "proceed"
                    elif overage:
                        can_proceed, action = True, "proceed_overage"
                    else:
                        can_proceed = False

                    if can_proceed:
                        new_balance = remaining - cost
                        await conn.execute(
                            "UPDATE users SET credits_remaining = $1 WHERE id = $2", new_balance, user_row["id"]
                        )
                        return {"can_proceed": True, "action": action, "credits_cost": cost, "remaining": new_balance, "success": True, "new_balance": new_balance, "deducted": cost}
                    else:
                        if remaining > 0:
                            return {"can_proceed": False, "action": "suggest_downgrade", "credits_cost": cost, "remaining": remaining, "suggested_mode": self.find_affordable_mode(remaining), "success": False, "reason": "insufficient_credits"}
                        return {"can_proceed": False, "action": "block", "credits_cost": cost, "remaining": remaining, "success": False, "reason": "insufficient_credits"}

    @with_db_retry()
    async def deduct(self, db_pool, workos_user_id: str, mode: str) -> dict:
        """Post-task atomic credit deduction using database function."""
        cost = self.CREDIT_COSTS.get(mode, 5)
        return await self.deduct_fixed(db_pool, workos_user_id, cost)

    @with_db_retry()
    async def deduct_fixed(self, db_pool, workos_user_id: str, cost: int) -> dict:
        """Post-task atomic credit deduction using an explicit cost amount."""
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Lock the user row to prevent race conditions and get team config
                user_row = await conn.fetchrow(
                    "SELECT id, team_id, credits_remaining, overage_enabled "
                    "FROM users WHERE workos_user_id = $1 FOR UPDATE",
                    workos_user_id,
                )
                if not user_row:
                    return {"success": False, "reason": "user_not_found"}

                overage = user_row["overage_enabled"]

                if user_row["team_id"]:
                    # Team Wallet Deduction
                    team_row = await conn.fetchrow(
                        "SELECT id, shared_credits_remaining, overage_enabled FROM teams WHERE id = $1 FOR UPDATE",
                        user_row["team_id"],
                    )
                    if not team_row:
                        return {"success": False, "reason": "team_not_found"}

                    team_overage = (
                        team_row["overage_enabled"] if team_row["overage_enabled"] is not None else overage
                    )
                    new_balance = team_row["shared_credits_remaining"] - cost
                    if new_balance < 0 and not team_overage:
                        return {"success": False, "reason": "insufficient_team_credits"}

                    await conn.execute(
                        "UPDATE teams SET shared_credits_remaining = $1 WHERE id = $2", new_balance, team_row["id"]
                    )
                    return {"success": True, "new_balance": new_balance, "deducted": cost}
                else:
                    # Solo User Deduction
                    new_balance = user_row["credits_remaining"] - cost
                    if new_balance < 0 and not overage:
                        return {"success": False, "reason": "insufficient_credits"}

                    await conn.execute(
                        "UPDATE users SET credits_remaining = $1 WHERE id = $2", new_balance, user_row["id"]
                    )
                    return {"success": True, "new_balance": new_balance, "deducted": cost}

    @with_db_retry()
    async def refund_fixed(self, db_pool, workos_user_id: str, cost: int) -> dict:
        """Refund a fixed credit amount after a failed upstream/provider call."""
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                user_row = await conn.fetchrow(
                    "SELECT id, team_id, credits_remaining FROM users WHERE workos_user_id = $1 FOR UPDATE",
                    workos_user_id,
                )
                if not user_row:
                    return {"success": False, "reason": "user_not_found"}

                if user_row["team_id"]:
                    team_row = await conn.fetchrow(
                        "SELECT id, shared_credits_remaining FROM teams WHERE id = $1 FOR UPDATE",
                        user_row["team_id"],
                    )
                    if not team_row:
                        return {"success": False, "reason": "team_not_found"}

                    new_balance = team_row["shared_credits_remaining"] + cost
                    await conn.execute(
                        "UPDATE teams SET shared_credits_remaining = $1 WHERE id = $2",
                        new_balance,
                        team_row["id"],
                    )
                    return {"success": True, "new_balance": new_balance, "refunded": cost}

                new_balance = user_row["credits_remaining"] + cost
                await conn.execute(
                    "UPDATE users SET credits_remaining = $1 WHERE id = $2",
                    new_balance,
                    user_row["id"],
                )
                return {"success": True, "new_balance": new_balance, "refunded": cost}

    async def replenish_monthly(self, db_pool, workos_user_id: str) -> dict:
        """Reset credits to plan allowance (called by Stripe webhook)."""
        row = await db_pool.fetchrow(
            "SELECT id, team_id, credits_monthly FROM users WHERE workos_user_id = $1",
            workos_user_id,
        )
        if not row:
            return {"error": "user not found"}

        monthly = row["credits_monthly"]
        if row["team_id"]:
            await db_pool.execute(
                "UPDATE teams SET shared_credits_remaining = $1 WHERE id = $2",
                monthly,
                row["team_id"],
            )
            return {"new_balance": monthly, "scope": "team"}

        await db_pool.execute(
            "UPDATE users SET credits_remaining = $1 WHERE id = $2",
            monthly,
            row["id"],
        )
        return {"new_balance": monthly, "scope": "user"}

    async def purchase_credits(self, db_pool, workos_user_id: str, amount: int) -> dict:
        """Add PAYG credits (called by Stripe webhook). PAYG credits never expire."""
        row = await db_pool.fetchrow(
            "SELECT id, team_id FROM users WHERE workos_user_id = $1",
            workos_user_id,
        )
        if not row:
            return {"error": "user not found"}

        if row["team_id"]:
            new_bal = await db_pool.fetchval(
                "UPDATE teams SET shared_credits_remaining = shared_credits_remaining + $1 WHERE id = $2 RETURNING shared_credits_remaining",  # noqa: E501
                amount,
                row["team_id"],
            )
            return {"new_balance": new_bal, "scope": "team"}

        new_bal = await db_pool.fetchval(
            "UPDATE users SET credits_remaining = credits_remaining + $1 WHERE id = $2 RETURNING credits_remaining",
            amount,
            row["id"],
        )
        return {"new_balance": new_bal, "scope": "user"}

    async def get_balance(self, db_pool, workos_user_id: str) -> dict:
        """Current credit status."""
        row = await db_pool.fetchrow(
            """
            SELECT u.plan, COALESCE(t.overage_enabled, u.overage_enabled) as effective_overage_enabled, u.credits_monthly,
                   COALESCE(t.shared_credits_remaining, u.credits_remaining, 0) as effective_credits
            FROM users u
            LEFT JOIN teams t ON u.team_id = t.id
            WHERE u.workos_user_id = $1
            """,
            workos_user_id,
        )
        if not row:
            return {}
        return {
            "credits_remaining": row["effective_credits"],
            "credits_monthly": row["credits_monthly"],
            "plan": row["plan"],
            "overage_enabled": row["effective_overage_enabled"],
        }

    def find_affordable_mode(self, credits: int) -> Optional[str]:
        """Find the best mode the user can afford."""
        for mode in ["scout", "standard", "battle", "ensemble", "architect"]:
            if self.CREDIT_COSTS[mode] <= credits:
                return mode
        return None
