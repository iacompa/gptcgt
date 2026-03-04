from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from api.services.encryption import _get_key
from proxy.main import verify_proxy_auth


def test_encryption_key_missing_fails_closed(monkeypatch):
    """Ensure misconfigured ENCRYPTION_KEY fails securely."""
    monkeypatch.setattr("api.services.encryption.settings.encryption_key", "")
    with pytest.raises(ValueError, match="must be a 64-character hex string"):
        _get_key()


def test_encryption_key_invalid_format_fails_closed(monkeypatch):
    """Ensure invalid format ENCRYPTION_KEY fails securely."""
    monkeypatch.setattr("api.services.encryption.settings.encryption_key", "Z" * 64)
    with pytest.raises(ValueError, match="Invalid ENCRYPTION_KEY format"):
        _get_key()


@pytest.mark.asyncio
async def test_proxy_auth_missing_header():
    """Ensure missing Bearer token is rejected."""
    request = MagicMock()
    request.headers.get.return_value = None
    with pytest.raises(HTTPException) as exc:
        await verify_proxy_auth(request)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_proxy_auth_invalid_jwt(monkeypatch):
    """Ensure invalid JWT is rejected."""
    # Mock settings / registry correctly for proxy tests
    monkeypatch.setattr("proxy.main.services.jwt.secret", "a" * 32)  # ≥32 chars required
    request = MagicMock()
    request.headers.get.return_value = "Bearer invalid.jwt.token"
    with pytest.raises(HTTPException) as exc:
        await verify_proxy_auth(request)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token"


@pytest.mark.asyncio
async def test_proxy_auth_missing_jwt_secret(monkeypatch):
    """Ensure missing JWT secret raises an exception appropriately."""
    monkeypatch.setattr("proxy.main.services.jwt.secret", "")
    request = MagicMock()
    request.headers.get.return_value = "Bearer some.jwt.token"
    # The ValueError should bubble up un-swallowed and get 500'd by the FastAPI handler
    with pytest.raises(ValueError, match="JWT_SECRET missing"):
        await verify_proxy_auth(request)


@pytest.mark.asyncio
async def test_proxy_auth_api_key_invalid(monkeypatch):
    """Ensure invalid sk-gptcgt- token fails via O(1) hash lookup."""
    request = MagicMock()
    request.headers.get.return_value = "Bearer sk-gptcgt-invalid"

    mock_pool = AsyncMock()
    mock_pool.fetchval.return_value = None  # DB finds no key_hash
    monkeypatch.setattr("proxy.main.get_pool", lambda: mock_pool)

    with pytest.raises(HTTPException) as exc:
        await verify_proxy_auth(request)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid API Key"
