from unittest.mock import AsyncMock

import pytest

from src.billing.credits import CreditService
from src.billing.spending_caps import SpendingCapService


@pytest.mark.asyncio
async def test_spending_cap_uses_usage_events_not_balance_deltas():
    svc = SpendingCapService()
    db_pool = AsyncMock()
    db_pool.fetchrow.return_value = {
        "spending_cap": 100.0,
        "credits_monthly": 1000,
        "credits_used_month": 3500,
    }

    status = await svc.get_cap_status(db_pool, "user_123")

    assert status["has_cap"] is True
    assert status["credits_used_month"] == 3500
    assert status["spent_dollars"] == 35.0
    assert status["percent_used"] == 35.0


@pytest.mark.asyncio
async def test_replenish_monthly_targets_team_wallet():
    svc = CreditService()
    db_pool = AsyncMock()
    db_pool.fetchrow.return_value = {
        "id": "user-internal",
        "team_id": "team-123",
        "credits_monthly": 2400,
    }

    result = await svc.replenish_monthly(db_pool, "user_123")

    db_pool.execute.assert_awaited_once_with(
        "UPDATE teams SET shared_credits_remaining = $1 WHERE id = $2",
        2400,
        "team-123",
    )
    assert result == {"new_balance": 2400, "scope": "team"}


@pytest.mark.asyncio
async def test_purchase_credits_targets_team_wallet():
    svc = CreditService()
    db_pool = AsyncMock()
    db_pool.fetchrow.return_value = {
        "id": "user-internal",
        "team_id": "team-123",
    }
    db_pool.fetchval.return_value = 3100

    result = await svc.purchase_credits(db_pool, "user_123", 500)

    db_pool.fetchval.assert_awaited_once_with(
        "UPDATE teams SET shared_credits_remaining = shared_credits_remaining + $1 WHERE id = $2 RETURNING shared_credits_remaining",
        500,
        "team-123",
    )
    assert result == {"new_balance": 3100, "scope": "team"}


@pytest.mark.asyncio
async def test_get_balance_prefers_effective_team_overage():
    svc = CreditService()
    db_pool = AsyncMock()
    db_pool.fetchrow.return_value = {
        "plan": "team",
        "effective_overage_enabled": True,
        "credits_monthly": 2400,
        "effective_credits": 1800,
    }

    balance = await svc.get_balance(db_pool, "user_123")

    assert balance == {
        "credits_remaining": 1800,
        "credits_monthly": 2400,
        "plan": "team",
        "overage_enabled": True,
    }
