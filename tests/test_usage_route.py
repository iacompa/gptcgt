from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from api.routes import usage


@pytest.mark.asyncio
async def test_usage_route_expands_limit_for_ranged_queries(monkeypatch):
    pool = AsyncMock()
    pool.fetchval.return_value = "internal-user"
    pool.fetch.return_value = []
    monkeypatch.setattr("api.routes.usage.get_pool", lambda: pool)

    request = SimpleNamespace(state=SimpleNamespace(user_id="workos-user"))
    result = await usage.get_usage(
        request,
        start_date="2026-03-01T00:00:00",
        end_date="2026-03-31T23:59:59",
    )

    query = pool.fetch.await_args.args[0]
    args = pool.fetch.await_args.args[1:]
    assert "created_at >=" in query
    assert "created_at <=" in query
    assert args[-1] == usage.RANGED_LIMIT
    assert result == []


@pytest.mark.asyncio
async def test_usage_route_rejects_invalid_dates(monkeypatch):
    pool = AsyncMock()
    monkeypatch.setattr("api.routes.usage.get_pool", lambda: pool)

    request = SimpleNamespace(state=SimpleNamespace(user_id="workos-user"))
    with pytest.raises(HTTPException) as exc_info:
        await usage.get_usage(request, start_date="not-a-date")

    assert exc_info.value.status_code == 400
    assert "start_date" in exc_info.value.detail
