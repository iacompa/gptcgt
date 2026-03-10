from unittest.mock import AsyncMock

import pytest

from src.billing.stripe_service import StripeService


@pytest.mark.asyncio
async def test_handle_checkout_syncs_team_seat_quantity(monkeypatch):
    service = StripeService()
    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        {"email": "owner@example.com"},
        {"team_id": "team-123"},
    ]

    track_async = AsyncMock()
    monkeypatch.setattr("src.services.analytics.track_async", track_async)
    monkeypatch.setattr("src.services.email.email_service.send_subscription_started", AsyncMock())

    actions = await service._handle_checkout(
        conn,
        {
            "client_reference_id": "user_123",
            "customer": "cus_123",
            "subscription": "sub_123",
            "metadata": {"type": "subscription", "plan": "team", "quantity": "3"},
        },
    )

    team_updates = [
        call
        for call in conn.execute.await_args_list
        if "UPDATE teams" in call.args[0]
    ]
    assert team_updates
    assert team_updates[0].args[1:] == (6000, "team", 3, "team-123")
    assert len(actions) == 2

    for _, action in actions:
        await action()

    track_async.assert_awaited_once_with("user_123", "subscription_started", {"plan": "team"})


@pytest.mark.asyncio
async def test_subscription_update_syncs_team_seat_count():
    service = StripeService()
    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        {"plan": "team"},
        {"team_id": "team-123"},
    ]

    await service._handle_subscription_update(
        conn,
        {
            "customer": "cus_123",
            "status": "active",
            "current_period_end": 1710000000,
            "items": {"data": [{"quantity": 4}]},
        },
    )

    team_updates = [
        call
        for call in conn.execute.await_args_list
        if "UPDATE teams" in call.args[0]
    ]
    assert team_updates
    assert team_updates[0].args[1:] == ("team", 4, "team-123")


@pytest.mark.asyncio
async def test_subscription_cancel_resets_team_seat_count(monkeypatch):
    service = StripeService()
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "workos_user_id": "user_123",
        "email": "owner@example.com",
        "team_id": "team-123",
    }

    track_async = AsyncMock()
    monkeypatch.setattr("src.services.analytics.track_async", track_async)

    actions = await service._handle_subscription_cancel(
        conn,
        {"customer": "cus_123"},
    )

    team_updates = [
        call
        for call in conn.execute.await_args_list
        if "UPDATE teams" in call.args[0]
    ]
    assert team_updates
    assert team_updates[0].args[1:] == ("team-123",)
    assert "seats_purchased = 1" in team_updates[0].args[0]
    assert len(actions) == 1
    await actions[0][1]()
    track_async.assert_awaited_once_with("user_123", "subscription_canceled", {})


@pytest.mark.asyncio
async def test_handle_webhook_post_commit_side_effect_failures_do_not_abort(monkeypatch):
    service = StripeService()

    class FakeTransaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeConn:
        def transaction(self):
            return FakeTransaction()

        async def execute(self, *args, **kwargs):
            return None

        async def fetchrow(self, query, *args):
            if "webhook_events" in query:
                return {"status": "received"}
            if "SELECT email FROM users WHERE workos_user_id" in query:
                return {"email": "owner@example.com"}
            if "SELECT team_id FROM users WHERE workos_user_id" in query:
                return {"team_id": "team-123"}
            return None

    class FakeAcquire:
        def __init__(self, conn):
            self.conn = conn

        async def __aenter__(self):
            return self.conn

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePool:
        def __init__(self):
            self.conn = FakeConn()

        def acquire(self):
            return FakeAcquire(self.conn)

    payload = b"{}"
    event = {
        "id": "evt_123",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": "user_123",
                "customer": "cus_123",
                "subscription": "sub_123",
                "metadata": {"type": "subscription", "plan": "team", "quantity": "2"},
            }
        },
    }

    monkeypatch.setattr("src.billing.stripe_service.stripe.Webhook.construct_event", lambda *args: event)
    monkeypatch.setattr(
        "src.services.email.email_service.send_subscription_started",
        AsyncMock(side_effect=RuntimeError("email down")),
    )
    track_async = AsyncMock()
    monkeypatch.setattr("src.services.analytics.track_async", track_async)

    result = await service.handle_webhook(FakePool(), payload, "sig")

    assert result == {"status": "success"}
    track_async.assert_awaited_once_with("user_123", "subscription_started", {"plan": "team"})
