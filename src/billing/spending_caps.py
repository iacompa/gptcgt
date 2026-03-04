import time

# Canonical credit-to-dollar conversion rate — MUST match billing.py and proxy
# 1 credit = $0.04 (aligned with Stripe checkout pricing)
CREDIT_TO_DOLLAR = 0.04


class SpendingCapService:
    """
    Server-side spending cap enforcement (API backend only).  # noqa: D204

    This service is used by the gptcgt API server to enforce per-user spending caps.
    It requires a PostgreSQL connection pool (asyncpg) and is NOT used in the desktop TUI app.
    """

    _cap_warned_users: dict[str, float] = {}  # user_id -> timestamp of last warning
    _CAP_WARN_COOLDOWN = 86400  # 24 hours in seconds

    THRESHOLDS = [
        (0.80, "yellow", "warning"),
        (0.95, "orange", "critical"),
        (1.00, "red", "blocked"),
    ]

    async def get_cap_status(self, db_pool, workos_user_id: str) -> dict:
        """Current spend vs cap."""
        row = await db_pool.fetchrow(
            """
            SELECT u.spending_cap, u.credits_monthly,
                   COALESCE(t.shared_credits_remaining, u.credits_remaining, 0) as effective_credits
            FROM users u
            LEFT JOIN teams t ON u.team_id = t.id
            WHERE u.workos_user_id = $1
            """,
            workos_user_id,
        )
        if not row:
            return {"has_cap": False, "warning_level": None}

        cap = row["spending_cap"]
        if not cap:
            return {"has_cap": False, "warning_level": None}

        monthly = row["credits_monthly"]
        remaining = row["effective_credits"]
        used = monthly - remaining
        spent_dollars = used * CREDIT_TO_DOLLAR
        pct = spent_dollars / cap if cap > 0 else 0

        warning_level = None
        for threshold, color, level in self.THRESHOLDS:
            if pct >= threshold:
                warning_level = level

        return {
            "has_cap": True,
            "cap_dollars": cap,
            "spent_dollars": round(spent_dollars, 2),
            "percent_used": round(pct * 100, 1),
            "warning_level": warning_level,
        }

    async def check_before_task(self, db_pool, workos_user_id: str, estimated_credits: int) -> dict:
        """Pre-task cap check. Returns whether task should proceed."""
        status = await self.get_cap_status(db_pool, workos_user_id)
        if not status["has_cap"]:
            return {"allowed": True}

        estimated_cost = estimated_credits * CREDIT_TO_DOLLAR
        projected = status["spent_dollars"] + estimated_cost

        if projected > status["cap_dollars"]:
            from src.services.analytics import track_async

            await track_async(
                workos_user_id, "spending_cap_hit", {"cap_dollars": status["cap_dollars"]}
            )

            # Send cap warning email (at most once per 24 hours per user)
            last_warned = self._cap_warned_users.get(workos_user_id, 0)
            if time.time() - last_warned > self._CAP_WARN_COOLDOWN:
                from src.services.email import email_service

                user_row = await db_pool.fetchrow(
                    "SELECT email FROM users WHERE workos_user_id = $1", workos_user_id
                )
                if user_row:
                    await email_service.send_warning_cap(user_row["email"], status["cap_dollars"])
                self._cap_warned_users[workos_user_id] = time.time()

            return {
                "allowed": False,
                "reason": "spending_cap_exceeded",
                "cap_dollars": status["cap_dollars"],
                "spent_dollars": status["spent_dollars"],
                "suggested_mode": "scout",
            }
        return {"allowed": True, "warning_level": status.get("warning_level")}

    async def set_cap(self, db_pool, workos_user_id: str, cap_dollars: int) -> None:
        """Set spending cap in dollars."""
        await db_pool.execute(
            "UPDATE users SET spending_cap = $1 WHERE workos_user_id = $2",
            cap_dollars,
            workos_user_id,
        )

    async def remove_cap(self, db_pool, workos_user_id: str) -> None:
        """Remove spending cap (unlimited)."""
        await db_pool.execute(
            "UPDATE users SET spending_cap = NULL WHERE workos_user_id = $1", workos_user_id
        )
