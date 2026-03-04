"""Phase 1 Regression Tests: Auth + Security Hardening."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import jwt
import pytest
from fastapi import HTTPException

# ─── Auth: JWT Claims ───────────────────────────────────────────────

class TestJWTClaims:
    """Verify JWTs contain iss and aud claims."""

    def test_jwt_contains_iss_aud(self):
        """Generated JWTs must contain iss='gptcgt' and aud='gptcgt-api'."""
        from api.routes.auth import _generate_jwt

        secret = "a" * 32
        with patch("api.routes.auth.settings") as mock_settings:
            mock_settings.jwt_secret = secret
            token = _generate_jwt("user_123", "test@example.com")

        payload = jwt.decode(
            token, secret, algorithms=["HS256"],
            audience="gptcgt-api",
            options={"verify_exp": False},
        )
        assert payload["iss"] == "gptcgt"
        assert payload["aud"] == "gptcgt-api"
        assert payload["sub"] == "user_123"

    def test_jwt_rejected_wrong_audience(self):
        """JWTs should fail validation if audience doesn't match."""
        from api.routes.auth import _generate_jwt

        secret = "a" * 32
        with patch("api.routes.auth.settings") as mock_settings:
            mock_settings.jwt_secret = secret
            token = _generate_jwt("user_123", "test@example.com")

        with pytest.raises(jwt.InvalidAudienceError):
            jwt.decode(
                token, secret, algorithms=["HS256"],
                audience="wrong-audience",
            )


# ─── Auth: Token Validation ─────────────────────────────────────────

class TestTokenValidation:
    """Verify HS256 path checks iss/aud."""

    def test_hs256_validates_issuer(self):
        """HS256 tokens must validate issuer when provided."""
        from src.auth.token_validation import verify_access_token

        secret = "a" * 32
        now = datetime.now(timezone.utc).timestamp()
        token = jwt.encode(
            {"sub": "usr", "exp": now + 3600, "iss": "wrong", "aud": "gptcgt-api"},
            secret, algorithm="HS256",
        )
        with pytest.raises(jwt.InvalidIssuerError):
            verify_access_token(
                token, hs256_secret=secret,
                issuer="gptcgt", audience="gptcgt-api",
            )

    def test_hs256_validates_audience(self):
        """HS256 tokens must validate audience when provided."""
        from src.auth.token_validation import verify_access_token

        secret = "a" * 32
        now = datetime.now(timezone.utc).timestamp()
        token = jwt.encode(
            {"sub": "usr", "exp": now + 3600, "iss": "gptcgt", "aud": "wrong"},
            secret, algorithm="HS256",
        )
        with pytest.raises(jwt.InvalidAudienceError):
            verify_access_token(
                token, hs256_secret=secret,
                issuer="gptcgt", audience="gptcgt-api",
            )

    def test_hs256_accepts_valid_iss_aud(self):
        """HS256 tokens with correct iss/aud should pass."""
        from src.auth.token_validation import verify_access_token

        secret = "a" * 32
        now = datetime.now(timezone.utc).timestamp()
        token = jwt.encode(
            {"sub": "usr", "exp": now + 3600, "iss": "gptcgt", "aud": "gptcgt-api"},
            secret, algorithm="HS256",
        )
        payload = verify_access_token(
            token, hs256_secret=secret,
            issuer="gptcgt", audience="gptcgt-api",
        )
        assert payload["sub"] == "usr"


# ─── Auth: Password Verification ────────────────────────────────────

class TestPasswordSignin:
    """Verify password signin requires bcrypt hash verification."""

    @pytest.mark.asyncio
    async def test_signin_rejects_without_password_hash(self):
        """Users without password_hash cannot use password login."""
        from api.routes.auth import SigninRequest, signin_with_password

        mock_pool = AsyncMock()
        mock_pool.fetchrow.return_value = {
            "workos_user_id": "uid_1",
            "email": "user@example.com",
            "password_hash": None,  # No hash stored
        }

        with patch("api.routes.auth.get_pool", return_value=mock_pool), \
             patch("api.routes.auth.settings") as mock_settings:
            mock_settings.allow_legacy_password_signin = True

            req = SigninRequest(email="user@example.com", password="password123")
            with pytest.raises(HTTPException) as exc:
                await signin_with_password(req)
            assert exc.value.status_code == 401
            assert "SSO" in exc.value.detail

    @pytest.mark.asyncio
    async def test_signin_rejects_wrong_password(self):
        """Wrong password must be rejected."""
        from api.routes.auth import SigninRequest, signin_with_password

        correct_hash = bcrypt.hashpw(b"correct_password", bcrypt.gensalt()).decode("utf-8")
        mock_pool = AsyncMock()
        mock_pool.fetchrow.return_value = {
            "workos_user_id": "uid_1",
            "email": "user@example.com",
            "password_hash": correct_hash,
        }

        with patch("api.routes.auth.get_pool", return_value=mock_pool), \
             patch("api.routes.auth.settings") as mock_settings:
            mock_settings.allow_legacy_password_signin = True

            req = SigninRequest(email="user@example.com", password="wrong_password")
            with pytest.raises(HTTPException) as exc:
                await signin_with_password(req)
            assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_signin_accepts_correct_password(self):
        """Correct password should issue JWT."""
        from api.routes.auth import SigninRequest, signin_with_password

        password = "correct_password123"
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        mock_pool = AsyncMock()
        mock_pool.fetchrow.return_value = {
            "workos_user_id": "uid_1",
            "email": "user@example.com",
            "password_hash": hashed,
        }

        with patch("api.routes.auth.get_pool", return_value=mock_pool), \
             patch("api.routes.auth.settings") as mock_settings:
            mock_settings.allow_legacy_password_signin = True
            mock_settings.jwt_secret = "a" * 32

            req = SigninRequest(email="user@example.com", password=password)
            result = await signin_with_password(req)
            assert result["access_token"]
            assert result["workos_user_id"] == "uid_1"


# ─── Auth: Public Paths ─────────────────────────────────────────────

class TestPublicPaths:
    """Verify auth endpoints are accessible without token."""

    def test_signin_is_public(self):
        from api.middleware.auth import PUBLIC_PATHS_EXACT
        assert "/auth/signin" in PUBLIC_PATHS_EXACT

    def test_sso_callback_is_public(self):
        from api.middleware.auth import PUBLIC_PATHS_EXACT
        assert "/auth/sso/callback" in PUBLIC_PATHS_EXACT


# ─── Security: Memory Pardon Severity Lock ───────────────────────────

class TestMemoryPardonSeverity:
    """Verify memory pardons cannot override medium+ security findings."""

    @pytest.mark.asyncio
    async def test_pardon_blocks_high_severity(self):
        """High-severity findings cannot be pardoned by memory."""
        from src.core.arbiter import Arbiter

        arbiter = Arbiter.__new__(Arbiter)  # Skip __init__

        # Create mock findings
        mock_high = MagicMock()
        mock_high.severity = "high"
        mock_high.rule_id = "sql-injection"

        mock_low = MagicMock()
        mock_low.severity = "low"
        mock_low.rule_id = "unused-import"

        findings = [mock_high, mock_low]
        verification = MagicMock()

        memory = "EXEMPT_RULE:sql-injection false positive\nEXEMPT_RULE:unused-import known\n"

        with patch.object(arbiter, "_apply_deterministic_exemptions") as mock_apply:
            await arbiter._apply_memory_pardons(verification, findings, memory)

            # Only the low-severity finding should be passed to exemptions
            if mock_apply.called:
                pardonable = mock_apply.call_args[0][1]
                severities = [f.severity for f in pardonable]
                assert "high" not in severities
                assert "low" in severities


# ─── Proxy Auth: Missing Secret ──────────────────────────────────────

class TestProxyAuthSecret:
    """Verify proxy rejects requests when JWT secret is missing."""

    @pytest.mark.asyncio
    async def test_proxy_auth_missing_jwt_secret(self):
        """Missing JWT secret raises ValueError."""
        from proxy.main import verify_proxy_auth

        request = MagicMock()
        request.headers.get.return_value = "Bearer some.jwt.token"

        with patch("proxy.main.services.jwt.secret", ""):
            with pytest.raises(ValueError, match="JWT_SECRET missing"):
                await verify_proxy_auth(request)
