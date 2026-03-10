import json
from datetime import datetime, timedelta, timezone


class ModerationService:
    async def check_user_status(self, db_pool, workos_user_id: str) -> dict:
        """Returns user moderation status: active, suspended, or banned."""
        row = await db_pool.fetchrow(
            "SELECT suspended_at, suspended_until, suspended_reason FROM users WHERE workos_user_id = $1",  # noqa: E501
            workos_user_id,
        )
        if not row or not row["suspended_at"]:
            return {"status": "active"}

        if row["suspended_until"] and row["suspended_until"] < datetime.now(timezone.utc):
            # Auto-lift expired suspension
            await self.lift_suspension(db_pool, workos_user_id)
            return {"status": "active"}

        if row["suspended_reason"] and "permanent" in row["suspended_reason"].lower():
            return {"status": "banned", "reason": row["suspended_reason"]}

        return {
            "status": "suspended",
            "reason": row["suspended_reason"],
            "until": row["suspended_until"].isoformat() if row["suspended_until"] else None,
        }

    async def suspend_user(self, db_pool, workos_user_id: str, reason: str, duration_hours: int = 24) -> None:
        """Temporary suspension."""
        until = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
        await db_pool.execute(
            "UPDATE users SET suspended_at = now(), suspended_until = $1, suspended_reason = $2 WHERE workos_user_id = $3",  # noqa: E501
            until,
            reason,
            workos_user_id,
        )
        # Log to audit_log
        internal_id = await db_pool.fetchval("SELECT id FROM users WHERE workos_user_id = $1", workos_user_id)
        if internal_id:
            await db_pool.execute(
                "INSERT INTO audit_log (user_id, action, details) VALUES ($1, 'suspend', $2)",
                internal_id,
                json.dumps({"reason": reason, "duration_hours": duration_hours}),
            )

    async def ban_user(self, db_pool, workos_user_id: str, reason: str) -> None:
        """Permanent ban."""
        await db_pool.execute(
            "UPDATE users SET suspended_at = now(), suspended_until = NULL, suspended_reason = $1 WHERE workos_user_id = $2",  # noqa: E501
            f"permanent: {reason}",
            workos_user_id,
        )
        internal_id = await db_pool.fetchval("SELECT id FROM users WHERE workos_user_id = $1", workos_user_id)
        if internal_id:
            await db_pool.execute(
                "INSERT INTO audit_log (user_id, action, details) VALUES ($1, 'ban', $2)",
                internal_id,
                json.dumps({"reason": reason}),
            )

    async def lift_suspension(self, db_pool, workos_user_id: str) -> None:
        """Lift suspension."""
        await db_pool.execute(
            "UPDATE users SET suspended_at = NULL, suspended_until = NULL, suspended_reason = NULL WHERE workos_user_id = $1",  # noqa: E501
            workos_user_id,
        )

    async def auto_lift_expired(self, db_pool) -> int:
        """Cron-callable: lift all expired suspensions. Returns count lifted."""
        result = await db_pool.execute(
            "UPDATE users SET suspended_at = NULL, suspended_until = NULL, suspended_reason = NULL "
            "WHERE suspended_at IS NOT NULL AND suspended_until IS NOT NULL AND suspended_until < now()"  # noqa: E501
        )
        return int(result.split()[-1])  # "UPDATE N"

    async def record_abuse_event(self, db_pool, workos_user_id: str, category: str, details: str) -> None:
        """Log abuse for review."""
        internal_id = await db_pool.fetchval("SELECT id FROM users WHERE workos_user_id = $1", workos_user_id)
        if internal_id:
            await db_pool.execute(
                "INSERT INTO audit_log (user_id, action, details) VALUES ($1, 'abuse_report', $2)",
                internal_id,
                json.dumps({"category": category, "details": details}),
            )
