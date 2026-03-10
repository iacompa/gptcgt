import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app


@pytest.fixture
async def mock_auth(monkeypatch):
    """Mock get_current_user yielding a known user ID."""
    user_id = str(uuid.uuid4())

    async def mock_get_current_user():
        return user_id

    # Mock verify_access_token so AuthMiddleware accepts our fake token
    monkeypatch.setattr(
        "api.middleware.auth.verify_access_token",
        lambda *args, **kwargs: {"sub": user_id, "email": "test@gptcgt.ai"}
    )

    return user_id

@pytest.fixture
async def mock_db(monkeypatch, mock_auth):
    class MockConnection:
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass

        class Transaction:
            async def __aenter__(self): return self
            async def __aexit__(self, exc_type, exc, tb): pass

        def transaction(self):
            return self.Transaction()

        async def execute(self, query, *args):
            if "UPDATE api_keys SET is_active = false" in query:
                # The real endpoint passes native_id (int from DB), not workos_user_id
                assert args[0] == 999
            elif "UPDATE users" in query:
                assert str(args[0]).startswith("deleted_")
                assert str(args[1]).startswith("deleted_999")
                assert args[2] == 999

        async def fetchrow(self, query, *args):
            if "SELECT workos_user_id" in query:
                return {"workos_user_id": mock_auth}
            if "suspended_at" in query:
                return {"suspended_at": None, "suspended_until": None, "suspended_reason": None}
            if "COALESCE" in query:
                return {"credits": 1000, "overage_enabled": False}
            return None


    class MockPool:
        def acquire(self):
            return MockConnection()

        async def fetchrow(self, query, *args):
            if "SELECT workos_user_id FROM users WHERE workos_user_id = $1" in query:
                return {"workos_user_id": mock_auth}
            if "SELECT is_suspended" in query:
                return {"is_suspended": False, "suspension_reason": None}
            if "SELECT id, email FROM users" in query:
                return {"id": 999, "email": "test@gptcgt.ai"}
            return None

    pool = MockPool()
    monkeypatch.setattr("api.routes.users.get_pool", lambda: pool)
    monkeypatch.setattr("api.middleware.auth.get_pool", lambda: pool)
    return pool

@pytest.mark.asyncio
async def test_delete_user_me(mock_auth, mock_db):
    """Test that DELETE /user/me correctly sanitizes the user identity."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer fake_token"}
    ) as client:
        response = await client.delete("/user/me")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["message"] == "Account securely deleted"

@pytest.mark.asyncio
async def test_delete_user_not_found(mock_auth, monkeypatch):
    """Test that DELETE /user/me 404s if the internal DB ID lookup fails."""
    class MockEmptyPool:
        def acquire(self):
            class MockConn:
                async def __aenter__(self): return self
                async def __aexit__(self, exc_type, exc, tb): pass
                async def fetchrow(self, query, *args):
                    if "SELECT workos_user_id" in query:
                        return {"workos_user_id": mock_auth}
                    if "SELECT is_suspended" in query:
                        return {"is_suspended": False, "suspension_reason": None}
                    return None
            return MockConn()

        async def fetchrow(self, query, *args):
            if "SELECT workos_user_id FROM users WHERE workos_user_id = $1" in query:
                return {"workos_user_id": mock_auth}
            if "SELECT is_suspended" in query:
                return {"is_suspended": False, "suspension_reason": None}
            return None

    monkeypatch.setattr("api.routes.users.get_pool", lambda: MockEmptyPool())
    monkeypatch.setattr("api.middleware.auth.get_pool", lambda: MockEmptyPool())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer fake_token"}
    ) as client:
        response = await client.delete("/user/me")
        assert response.status_code == 404
