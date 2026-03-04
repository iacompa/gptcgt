from typing import Optional


class CreditService:
    CREDIT_COSTS = {
        "scout": 1,
        "standard": 5,
        "ensemble": 25,
        "architect": 100,
        "battle": 25,
        "sandbox": 1,
    }

    async def check_credits(self, db_pool, workos_user_id: str, mode: str) -> dict:
        """Pre-task check: can user afford this mode? Checks team wallet if applicable."""
        cost = self.CREDIT_COSTS.get(mode, 5)
        row = await db_pool.fetchrow(
            """
            SELECT u.id, u.overage_enabled, u.plan, u.allocated_quota, u.team_id,
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

    async def deduct(self, db_pool, workos_user_id: str, mode: str) -> dict:
        """Post-task atomic credit deduction using database function."""
        cost = self.CREDIT_COSTS.get(mode, 5)

        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Lock the user row to prevent race conditions and get team config
                user_row = await conn.fetchrow(
                    "SELECT id, team_id, credits_remaining FROM users WHERE workos_user_id = $1 FOR UPDATE",
                    workos_user_id,
                )
                if not user_row:
                    return {"success": False, "reason": "user_not_found"}

                if user_row["team_id"]:
                    # Team Wallet Deduction
                    team_row = await conn.fetchrow(
                        "SELECT id, shared_credits_remaining FROM teams WHERE id = $1 FOR UPDATE",
                        user_row["team_id"]
                    )
                    if not team_row:
                        return {"success": False, "reason": "team_not_found"}
                    
                    new_balance = team_row["shared_credits_remaining"] - cost
                    if new_balance < 0:
                        return {"success": False, "reason": "insufficient_team_credits"}
                    
                    await conn.execute(
                        "UPDATE teams SET shared_credits_remaining = $1 WHERE id = $2", 
                        new_balance, team_row["id"]
                    )
                    return {"success": True, "new_balance": new_balance, "deducted": cost}
                else:
                    # Solo User Deduction
                    new_balance = user_row["credits_remaining"] - cost
                    if new_balance < 0:
                        return {"success": False, "reason": "insufficient_credits"}

                    await conn.execute(
                        "UPDATE users SET credits_remaining = $1 WHERE id = $2", new_balance, user_row["id"]
                    )
                    return {"success": True, "new_balance": new_balance, "deducted": cost}

    async def replenish_monthly(self, db_pool, workos_user_id: str) -> dict:
        """Reset credits to plan allowance (called by Stripe webhook)."""
        row = await db_pool.fetchrow(
            "SELECT credits_monthly FROM users WHERE workos_user_id = $1", workos_user_id
        )
        if not row:
            return {"error": "user not found"}

        monthly = row["credits_monthly"]
        await db_pool.execute(
            "UPDATE users SET credits_remaining = $1 WHERE workos_user_id = $2",
            monthly,
            workos_user_id,
        )
        return {"new_balance": monthly}

    async def purchase_credits(self, db_pool, workos_user_id: str, amount: int) -> dict:
        """Add PAYG credits (called by Stripe webhook). PAYG credits never expire."""
        new_bal = await db_pool.fetchval(
            "UPDATE users SET credits_remaining = credits_remaining + $1 WHERE workos_user_id = $2 RETURNING credits_remaining",  # noqa: E501
            amount,
            workos_user_id,
        )
        return {"new_balance": new_bal}


    async def get_balance(self, db_pool, workos_user_id: str) -> dict:
        """Current credit status."""
        row = await db_pool.fetchrow(
            """
            SELECT u.plan, u.overage_enabled, u.credits_monthly,
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
            "overage_enabled": row["overage_enabled"],
        }

    def find_affordable_mode(self, credits: int) -> Optional[str]:
        """Find the best mode the user can afford."""
        for mode in ["architect", "ensemble", "battle", "standard", "scout"]:
            if self.CREDIT_COSTS[mode] <= credits:
                return mode
        return None
