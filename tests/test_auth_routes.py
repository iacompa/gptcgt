import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import jwt
import pytest

from api.routes import auth


def _fake_workos_result(user_id="user_123", email="dev@example.com", refresh_token="refresh_123"):
    user = SimpleNamespace(
        id=user_id,
        email=email,
        first_name="Dev",
        last_name="User",
    )
    return SimpleNamespace(user=user, refresh_token=refresh_token)


@pytest.mark.asyncio
async def test_start_device_flow_returns_local_verification_uri(monkeypatch):
    class FakePool:
        def __init__(self):
            self.args = None

        async def fetchval(self, query, *args):
            self.args = args
            return "session-123"

    pool = FakePool()
    monkeypatch.setattr("api.routes.auth.get_pool", lambda: pool)

    request = SimpleNamespace(base_url="https://api.example.com/")
    result = await auth.start_device_flow(request, client_id="client_test")

    assert result["verification_uri"].startswith("https://api.example.com/auth/device/authorize?user_code=")
    assert result["verification_uri_complete"] == result["verification_uri"]
    assert result["device_code"]
    assert result["user_code"]
    assert pool.args[0] == "client_test"
    assert pool.args[1] != result["device_code"]


@pytest.mark.asyncio
async def test_authorize_device_redirects_to_workos_user_management(monkeypatch):
    future = datetime.now(timezone.utc) + timedelta(minutes=5)

    class FakePool:
        async def fetchrow(self, query, *args):
            return {
                "id": "session-123",
                "state_nonce": "nonce-123",
                "status": "pending",
                "expires_at": future,
            }

    class FakeUserManagement:
        def __init__(self):
            self.kwargs = None

        def get_authorization_url(self, **kwargs):
            self.kwargs = kwargs
            return "https://api.workos.com/user_management/authorize?client_id=client"

    fake_um = FakeUserManagement()
    monkeypatch.setattr("api.routes.auth.get_pool", lambda: FakePool())
    monkeypatch.setattr(
        "api.routes.auth._get_workos_client",
        lambda: SimpleNamespace(user_management=fake_um),
    )
    monkeypatch.setattr(auth.settings, "base_url", "https://gptcgt.ai")

    request = SimpleNamespace(
        base_url="https://api.example.com/",
        url=SimpleNamespace(scheme="https"),
    )
    response = await auth.authorize_device(request, user_code="ABCD-EFGH")

    assert response.status_code == 302
    assert response.headers["location"] == "https://api.workos.com/user_management/authorize?client_id=client"
    assert fake_um.kwargs["redirect_uri"] == "https://gptcgt.ai/api/auth/callback"
    assert fake_um.kwargs["provider"] == "authkit"
    assert fake_um.kwargs["state"]


@pytest.mark.asyncio
async def test_get_token_reports_authorization_pending_for_pending_device_session(monkeypatch):
    future = datetime.now(timezone.utc) + timedelta(minutes=5)

    class FakePool:
        async def fetchrow(self, query, *args):
            return {
                "id": "session-123",
                "status": "pending",
                "expires_at": future,
                "encrypted_refresh_token": None,
                "workos_user_id": None,
                "email": None,
                "profile": {},
                "error": None,
            }

    monkeypatch.setattr("api.routes.auth.get_pool", lambda: FakePool())
    response = await auth.get_token(
        auth.TokenRequest(device_code="device-code"),
        SimpleNamespace(client=None, headers={}),
    )

    assert response.status_code == 400
    assert json.loads(response.body) == {"error": "authorization_pending"}


@pytest.mark.asyncio
async def test_complete_device_flow_authorizes_session(monkeypatch):
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    execute_calls = []
    state = auth._encode_device_state("session-123", "nonce-123")

    class FakePool:
        async def fetchrow(self, query, *args):
            return {
                "id": "session-123",
                "state_nonce": "nonce-123",
                "status": "pending",
                "expires_at": future,
            }

        async def execute(self, query, *args):
            execute_calls.append((query, args))

    monkeypatch.setattr("api.routes.auth.get_pool", lambda: FakePool())
    monkeypatch.setattr("api.routes.auth._exchange_code_for_tokens", AsyncMock(return_value=_fake_workos_result()))
    sync_user = AsyncMock()
    monkeypatch.setattr("api.routes.auth._sync_user", sync_user)

    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"user-agent": "pytest"},
    )
    response = await auth.complete_device_flow(request, code="auth-code", state=state)

    assert response.status_code == 200
    assert any("SET status = 'authorized'" in query for query, _ in execute_calls)
    sync_user.assert_awaited_once_with("user_123", "dev@example.com")
    assert "Return to the terminal" in response.body.decode()


@pytest.mark.asyncio
async def test_sso_callback_exchanges_code_with_user_management(monkeypatch):
    monkeypatch.setattr(auth.settings, "jwt_secret", "x" * 64)
    monkeypatch.setattr(auth.settings, "workos_issuer", "issuer.example")
    monkeypatch.setattr(auth.settings, "workos_audience", "aud.example")
    monkeypatch.setattr("api.routes.auth._exchange_code_for_tokens", AsyncMock(return_value=_fake_workos_result()))
    sync_user = AsyncMock()
    monkeypatch.setattr("api.routes.auth._sync_user", sync_user)

    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"user-agent": "pytest"},
    )
    result = await auth.sso_callback(auth.SSOCallbackRequest(code="auth-code"), request)
    payload = jwt.decode(
        result["access_token"],
        auth.settings.jwt_secret,
        algorithms=["HS256"],
        issuer="issuer.example",
        audience="aud.example",
    )

    assert payload["sub"] == "user_123"
    assert result["refresh_token"] == "refresh_123"
    assert result["email"] == "dev@example.com"
    sync_user.assert_awaited_once_with("user_123", "dev@example.com")


@pytest.mark.asyncio
async def test_refresh_token_uses_workos_user_management(monkeypatch):
    monkeypatch.setattr(auth.settings, "jwt_secret", "x" * 64)
    monkeypatch.setattr("api.routes.auth._refresh_workos_tokens", AsyncMock(return_value=_fake_workos_result(refresh_token="refresh_new")))
    sync_user = AsyncMock()
    monkeypatch.setattr("api.routes.auth._sync_user", sync_user)

    result = await auth.get_token(
        auth.TokenRequest(grant_type="refresh_token", refresh_token="refresh_old"),
        SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={"user-agent": "pytest"}),
    )

    assert result["refresh_token"] == "refresh_new"
    assert result["profile"]["email"] == "dev@example.com"
    sync_user.assert_awaited_once_with("user_123", "dev@example.com")
