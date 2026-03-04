from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from proxy.main import proxy_completions
from src.billing.spending_caps import SpendingCapService


@pytest.mark.asyncio
async def test_spending_cap_status_math():
    """Ensure math for cap threshold is deterministic."""
    svc = SpendingCapService()
    db_pool = AsyncMock()
    # Mock user who has a cap of $150 and has used 4000 credits.
    # 1 credit = $0.04 -> $160 spent = 4000 credits used.
    # If 5000 monthly, remaining = 1000
    db_pool.fetchrow.return_value = {
        "spending_cap": 150.0,
        "credits_monthly": 5000,
        "effective_credits": 1000,
    }

    status = await svc.get_cap_status(db_pool, "user_123")
    assert status["has_cap"] is True
    assert status["spent_dollars"] == 160.0
    assert status["cap_dollars"] == 150.0


@pytest.mark.asyncio
async def test_proxy_403_on_cap_exceed(monkeypatch):
    """Ensure proxy drops request with 403 when spending cap is exceeded."""
    # Mock credit service to say they have basic credits
    mock_credit_svc = AsyncMock()
    mock_credit_svc.check_credits.return_value = {
        "can_proceed": True,
        "credits_cost": 50,
        "remaining": 500,
    }
    monkeypatch.setattr("proxy.main.credit_service", mock_credit_svc)

    # Mock content filter
    mock_filter = MagicMock()
    mock_filter.map_messages.return_value = (True, "")
    monkeypatch.setattr("proxy.main.content_filter", mock_filter)

    # Mock spending cap to block
    mock_cap_svc = AsyncMock()
    mock_cap_svc.check_before_task.return_value = {
        "allowed": False,
        "reason": "cap_exceeded",
        "spent_dollars": 151.0,
    }
    monkeypatch.setattr("proxy.main.spending_caps", mock_cap_svc)

    monkeypatch.setattr("proxy.main.get_pool", lambda: AsyncMock())

    request = MagicMock()
    request.json = AsyncMock(return_value={"model": "gpt-4"})
    request.headers.get.return_value = "standard"

    with pytest.raises(HTTPException) as exc:
        await proxy_completions(request, user_id="u_1")

    assert exc.value.status_code == 403
    assert "Spending cap exceeded" in exc.value.detail


@pytest.mark.asyncio
async def test_proxy_402_on_zero_credits(monkeypatch):
    """Ensure proxy drops request with 402 Payment Required on zero balance."""
    mock_credit_svc = AsyncMock()
    mock_credit_svc.check_credits.return_value = {
        "can_proceed": False,
        "credits_cost": 50,
        "remaining": 5,
    }
    monkeypatch.setattr("proxy.main.credit_service", mock_credit_svc)

    mock_filter = MagicMock()
    mock_filter.map_messages.return_value = (True, "")
    monkeypatch.setattr("proxy.main.content_filter", mock_filter)

    monkeypatch.setattr("proxy.main.get_pool", lambda: AsyncMock())

    request = MagicMock()
    request.json = AsyncMock(return_value={"model": "gpt-4"})
    request.headers.get.return_value = "standard"

    with pytest.raises(HTTPException) as exc:
        await proxy_completions(request, user_id="u_1")

    assert exc.value.status_code == 402
    assert "Insufficient credits" in exc.value.detail
