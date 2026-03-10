import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from proxy.main import SandboxExecuteRequest, proxy_completions, proxy_sandbox_execute
from proxy.metering import UsageMeter
from src.billing.spending_caps import SpendingCapService


@pytest.mark.asyncio
async def test_spending_cap_status_math():
    """Ensure math for cap threshold is deterministic."""
    svc = SpendingCapService()
    db_pool = AsyncMock()
    # Mock user who has a cap of $150 and has used 4000 credits.
    # 1 credit = $0.01 -> $40 spent = 4000 credits used.
    # If 5000 monthly, remaining = 1000
    db_pool.fetchrow.return_value = {
        "spending_cap": 150.0,
        "credits_monthly": 5000,
        "credits_used_month": 4000,
    }

    status = await svc.get_cap_status(db_pool, "user_123")
    assert status["has_cap"] is True
    assert status["spent_dollars"] == 40.0
    assert status["cap_dollars"] == 150.0


@pytest.mark.asyncio
async def test_proxy_403_on_cap_exceed(monkeypatch):
    """Ensure proxy drops request with 403 when spending cap is exceeded."""
    # Mock credit service to say they have basic credits
    mock_credit_svc = MagicMock()
    mock_credit_svc.check_credits = AsyncMock(return_value={
        "can_proceed": True,
        "credits_cost": 50,
        "remaining": 500,
    })
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
    mock_credit_svc = MagicMock()
    mock_credit_svc.check_credits = AsyncMock(return_value={
        "can_proceed": False,
        "credits_cost": 50,
        "remaining": 5,
    })
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


@pytest.mark.asyncio
async def test_sandbox_provision_failure_does_not_deduct(monkeypatch):
    """Provisioning failures must not charge credits."""
    mock_credit_svc = MagicMock()
    mock_credit_svc.check_credits = AsyncMock(return_value={
        "can_proceed": True,
        "credits_cost": 1,
        "remaining": 50,
    })
    mock_credit_svc.deduct_fixed = AsyncMock(return_value={"success": True})
    monkeypatch.setattr("proxy.main.credit_service", mock_credit_svc)

    mock_cap_svc = AsyncMock()
    mock_cap_svc.check_before_task.return_value = {"allowed": True}
    monkeypatch.setattr("proxy.main.spending_caps", mock_cap_svc)

    monkeypatch.setattr("proxy.main.get_pool", lambda: AsyncMock())
    monkeypatch.setenv("E2B_API_KEY", "test-key")

    failing_module = types.ModuleType("e2b_code_interpreter")

    class FailingSandbox:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("provision failed")

    failing_module.Sandbox = FailingSandbox
    monkeypatch.setitem(sys.modules, "e2b_code_interpreter", failing_module)

    with pytest.raises(HTTPException) as exc:
        await proxy_sandbox_execute(
            SandboxExecuteRequest(
                files={"main.py": "print('hi')"},
                language="python",
                command="python main.py",
            ),
            user_id="u_1",
        )

    assert exc.value.status_code == 502
    mock_credit_svc.deduct_fixed.assert_not_awaited()


@pytest.mark.asyncio
async def test_proxy_upstream_error_refunds_reserved_credits(monkeypatch):
    """Provider failures after reservation should refund the reserved credits."""
    mock_credit_svc = MagicMock()
    mock_credit_svc.check_credits = AsyncMock(return_value={
        "can_proceed": True,
        "credits_cost": 5,
        "remaining": 50,
    })
    mock_credit_svc.check_and_deduct = AsyncMock(return_value={
        "can_proceed": True,
        "credits_cost": 5,
        "remaining": 45,
    })
    mock_credit_svc.refund_fixed = AsyncMock(return_value={"success": True, "new_balance": 50})
    monkeypatch.setattr("proxy.main.credit_service", mock_credit_svc)

    mock_filter = MagicMock()
    mock_filter.map_messages.return_value = (True, "")
    monkeypatch.setattr("proxy.main.content_filter", mock_filter)

    mock_cap_svc = AsyncMock()
    mock_cap_svc.check_before_task.return_value = {"allowed": True}
    monkeypatch.setattr("proxy.main.spending_caps", mock_cap_svc)
    monkeypatch.setattr("proxy.main.get_pool", lambda: AsyncMock())

    async def fail_completion(**kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr("proxy.main.acompletion", fail_completion)

    request = MagicMock()
    request.json = AsyncMock(return_value={"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]})
    request.headers.get.return_value = "standard"

    with pytest.raises(HTTPException) as exc:
        await proxy_completions(request, user_id="u_refund")

    assert exc.value.status_code == 502
    mock_credit_svc.check_and_deduct.assert_awaited_once()
    mock_credit_svc.refund_fixed.assert_awaited_once()


@pytest.mark.asyncio
async def test_sandbox_success_deducts_and_records_usage(monkeypatch):
    """Successful sandbox runs must bill once and write an immutable usage event."""
    mock_credit_svc = MagicMock()
    mock_credit_svc.check_credits = AsyncMock(return_value={
        "can_proceed": True,
        "credits_cost": 1,
        "remaining": 50,
    })
    mock_credit_svc.deduct_fixed = AsyncMock(return_value={"success": True, "new_balance": 49})
    monkeypatch.setattr("proxy.main.credit_service", mock_credit_svc)

    mock_cap_svc = AsyncMock()
    mock_cap_svc.check_before_task.return_value = {"allowed": True}
    monkeypatch.setattr("proxy.main.spending_caps", mock_cap_svc)

    db_pool = AsyncMock()
    monkeypatch.setattr("proxy.main.get_pool", lambda: db_pool)
    monkeypatch.setenv("E2B_API_KEY", "test-key")

    recorded = {}

    class FakeMeter:
        def __init__(self, mode, workos_user_id, cost_credits):
            recorded["mode"] = mode
            recorded["workos_user_id"] = workos_user_id
            recorded["cost_credits"] = cost_credits

        async def record_fixed_cost(self, event_type):
            recorded["event_type"] = event_type

    monkeypatch.setattr("proxy.main.UsageMeter", FakeMeter)

    success_module = types.ModuleType("e2b_code_interpreter")

    class FakeSandbox:
        def __init__(self, *args, **kwargs):
            self.files = MagicMock()
            self.commands = MagicMock()
            self.commands.run.return_value = types.SimpleNamespace(
                stdout="hello\n",
                stderr="",
                exit_code=0,
                duration_ms=123,
            )

        def kill(self):
            recorded["killed"] = True

    success_module.Sandbox = FakeSandbox
    monkeypatch.setitem(sys.modules, "e2b_code_interpreter", success_module)

    response = await proxy_sandbox_execute(
        SandboxExecuteRequest(
            files={"main.py": "print('hello')"},
            language="python",
            command="python main.py",
        ),
        user_id="u_success",
    )

    assert response["stdout"] == "hello\n"
    assert response["exit_code"] == 0
    mock_credit_svc.deduct_fixed.assert_awaited_once_with(db_pool, "u_success", 1)
    assert recorded == {
        "mode": "sandbox",
        "workos_user_id": "u_success",
        "cost_credits": 1,
        "event_type": "e2b_sandbox_run",
        "killed": True,
    }


@pytest.mark.asyncio
async def test_usage_meter_records_team_id(monkeypatch):
    """Usage events should capture team_id for shared-wallet analytics continuity."""
    db_pool = AsyncMock()
    db_pool.fetchrow.return_value = {"id": "user-internal", "team_id": "team-123"}
    monkeypatch.setattr("proxy.metering.get_pool", lambda: db_pool)

    meter = UsageMeter(mode="sandbox", workos_user_id="u_team", cost_credits=1)
    await meter.record_fixed_cost("e2b_sandbox_run")

    db_pool.execute.assert_awaited_once()
    args = db_pool.execute.await_args.args
    assert "INSERT INTO usage_events" in args[0]
    assert args[1] == "user-internal"
    assert args[2] == "team-123"
    assert args[3] == "sandbox"
    assert args[4] == 1
    assert args[5] == ["e2b_sandbox_run"]
    assert isinstance(args[6], int)
