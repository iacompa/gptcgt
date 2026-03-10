import html
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from workos import AsyncWorkOSClient
from workos.exceptions import AuthenticationException, BaseRequestException

from api.config import settings
from api.database import get_pool
from api.services.encryption import decrypt_key, encrypt_key

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"])

DEVICE_FLOW_TTL_SECONDS = 600
DEVICE_FLOW_INTERVAL_SECONDS = 5
DEVICE_STATE_AUDIENCE = "gptcgt-device-auth"
USER_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _jwt_issuer() -> str:
    issuer = getattr(settings, "workos_issuer", "")
    return issuer if isinstance(issuer, str) and issuer else "gptcgt"


def _jwt_audience() -> str:
    audience = getattr(settings, "workos_audience", "")
    return audience if isinstance(audience, str) and audience else "gptcgt-api"


def _generate_jwt(sub: str, email: str, ttl: int = 3600) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "iss": _jwt_issuer(),
        "aud": _jwt_audience(),
        "iat": now.timestamp(),
        "exp": now.timestamp() + ttl,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _get_workos_client() -> AsyncWorkOSClient:
    if not settings.workos_api_key or not settings.workos_client_id:
        raise HTTPException(status_code=503, detail="WorkOS is not configured")
    return AsyncWorkOSClient(
        api_key=settings.workos_api_key,
        client_id=settings.workos_client_id,
    )


def _hash_device_code(device_code: str) -> str:
    return sha256(device_code.encode("utf-8")).hexdigest()


def _generate_user_code() -> str:
    raw = "".join(secrets.choice(USER_CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def _encode_device_state(session_id: str, nonce: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sid": session_id,
        "nonce": nonce,
        "iss": _jwt_issuer(),
        "aud": DEVICE_STATE_AUDIENCE,
        "iat": now.timestamp(),
        "exp": (now + timedelta(seconds=DEVICE_FLOW_TTL_SECONDS)).timestamp(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _decode_device_state(state: str) -> dict:
    return jwt.decode(
        state,
        settings.jwt_secret,
        algorithms=["HS256"],
        issuer=_jwt_issuer(),
        audience=DEVICE_STATE_AUDIENCE,
    )


def _row_expires_at(row: dict) -> datetime:
    expires_at = row["expires_at"]
    if expires_at.tzinfo is None:
        return expires_at.replace(tzinfo=timezone.utc)
    return expires_at.astimezone(timezone.utc)


def _profile_from_user(user) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "name": " ".join(part for part in [user.first_name, user.last_name] if part) or user.email.split("@")[0],
    }


def _coerce_profile(raw_profile) -> dict:
    if isinstance(raw_profile, dict):
        return raw_profile
    if isinstance(raw_profile, str):
        try:
            return json.loads(raw_profile)
        except json.JSONDecodeError:
            return {}
    return {}


def _device_status_response(error: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": error})


def _device_html(title: str, message: str, status_code: int = 200) -> HTMLResponse:
    safe_title = html.escape(title)
    safe_message = html.escape(message)
    return HTMLResponse(
        status_code=status_code,
        content=(
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{safe_title}</title>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<style>"
            "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
            "background:#f5f3ef;color:#0f172a;margin:0;padding:32px;}"
            ".card{max-width:520px;margin:8vh auto;background:#fff;border:1px solid #e2ddd4;"
            "border-radius:24px;padding:32px;box-shadow:0 20px 60px rgba(15,23,42,.08);}"
            "h1{margin:0 0 12px;font-size:28px;line-height:1.1;}"
            "p{margin:0;color:#475569;font-size:16px;line-height:1.6;}"
            "</style></head><body>"
            f"<div class='card'><h1>{safe_title}</h1><p>{safe_message}</p></div>"
            "</body></html>"
        ),
    )


async def _exchange_code_for_tokens(*, code: str, ip_address: str | None, user_agent: str | None):
    client = _get_workos_client()
    return await client.user_management.authenticate_with_code(
        code=code,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def _refresh_workos_tokens(*, refresh_token: str, ip_address: str | None, user_agent: str | None):
    client = _get_workos_client()
    return await client.user_management.authenticate_with_refresh_token(
        refresh_token=refresh_token,
        ip_address=ip_address,
        user_agent=user_agent,
    )


class TokenRequest(BaseModel):
    client_id: Optional[str] = None
    device_code: Optional[str] = None
    grant_type: Optional[str] = None
    refresh_token: Optional[str] = None


@router.post("/device")
async def start_device_flow(request: Request, client_id: Optional[str] = None):
    """Initiates terminal login by minting a local device session."""
    resolved_client_id = client_id or settings.workos_client_id
    if not resolved_client_id:
        raise HTTPException(status_code=400, detail="Missing client_id in request or server config")

    pool = get_pool()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=DEVICE_FLOW_TTL_SECONDS)

    import asyncpg

    for _ in range(5):
        device_code = secrets.token_urlsafe(32)
        user_code = _generate_user_code()
        state_nonce = secrets.token_urlsafe(24)
        try:
            await pool.fetchval(
                """
                INSERT INTO device_auth_sessions (
                    client_id,
                    device_code_hash,
                    user_code,
                    state_nonce,
                    status,
                    expires_at
                )
                VALUES ($1, $2, $3, $4, 'pending', $5)
                RETURNING id
                """,
                resolved_client_id,
                _hash_device_code(device_code),
                user_code,
                state_nonce,
                expires_at,
            )
            verification_uri = (
                f"{str(request.base_url).rstrip('/')}/auth/device/authorize?user_code={user_code}"
            )
            return {
                "device_code": device_code,
                "user_code": user_code,
                "verification_uri": verification_uri,
                "verification_uri_complete": verification_uri,
                "expires_in": DEVICE_FLOW_TTL_SECONDS,
                "interval": DEVICE_FLOW_INTERVAL_SECONDS,
            }
        except asyncpg.UniqueViolationError:
            continue

    raise HTTPException(status_code=500, detail="Failed to allocate a login session")


@router.get("/device/authorize")
async def authorize_device(request: Request, user_code: str):
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, state_nonce, status, expires_at
        FROM device_auth_sessions
        WHERE user_code = $1
        """,
        user_code.strip().upper(),
    )
    if not row:
        return _device_html("Code not found", "This sign-in code is invalid or has already expired.", 404)

    if _row_expires_at(row) <= datetime.now(timezone.utc):
        await pool.execute(
            "UPDATE device_auth_sessions SET status = 'expired' WHERE id = $1 AND status = 'pending'",
            row["id"],
        )
        return _device_html("Code expired", "This sign-in code has expired. Start /login again from the terminal.", 410)

    if row["status"] != "pending":
        return _device_html("Code already used", "This sign-in request is no longer pending. Start /login again if needed.", 409)

    state = _encode_device_state(str(row["id"]), row["state_nonce"])
    redirect_uri = f"{settings.base_url.rstrip('/')}/api/auth/callback"
    auth_url = _get_workos_client().user_management.get_authorization_url(
        redirect_uri=redirect_uri,
        provider="authkit",
        state=state,
    )

    return RedirectResponse(auth_url, status_code=302)


@router.get("/device/callback")
async def complete_device_flow(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    if not state:
        return _device_html("Sign-in failed", "The authentication state was invalid. Start /login again.", 400)

    try:
        state_payload = _decode_device_state(state)
    except jwt.InvalidTokenError:
        return _device_html("Sign-in failed", "The authentication state was invalid. Start /login again.", 400)

    session_id = state_payload.get("sid")
    nonce = state_payload.get("nonce")
    if not session_id or not nonce:
        return _device_html("Sign-in failed", "The authentication state was incomplete. Start /login again.", 400)

    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, state_nonce, status, expires_at
        FROM device_auth_sessions
        WHERE id = $1
        """,
        session_id,
    )
    if not row or row["state_nonce"] != nonce:
        return _device_html("Sign-in failed", "This terminal login request is no longer valid.", 404)

    if _row_expires_at(row) <= datetime.now(timezone.utc):
        await pool.execute(
            "UPDATE device_auth_sessions SET status = 'expired', error = 'expired_token' WHERE id = $1",
            session_id,
        )
        return _device_html("Sign-in expired", "This terminal login request expired. Start /login again.", 410)

    if row["status"] != "pending":
        return _device_html("Sign-in finished", "This terminal login request is no longer waiting for approval.", 409)

    if error:
        await pool.execute(
            "UPDATE device_auth_sessions SET status = 'failed', error = $1 WHERE id = $2",
            error,
            session_id,
        )
        return _device_html("Sign-in cancelled", "Authentication was cancelled. You can return to the terminal and try again.")

    if not code:
        return _device_html("Sign-in failed", "WorkOS did not return an authorization code.", 400)

    try:
        result = await _exchange_code_for_tokens(
            code=code,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except AuthenticationException as exc:
        logger.warning("WorkOS device code exchange failed: %s", exc)
        await pool.execute(
            "UPDATE device_auth_sessions SET status = 'failed', error = $1 WHERE id = $2",
            exc.error or "access_denied",
            session_id,
        )
        return _device_html("Sign-in failed", "The login could not be completed. Start /login again.")
    except BaseRequestException as exc:
        logger.error("WorkOS device code exchange error: %s", exc)
        await pool.execute(
            "UPDATE device_auth_sessions SET status = 'failed', error = $1 WHERE id = $2",
            exc.error or "workos_error",
            session_id,
        )
        return _device_html("Sign-in failed", "The identity provider returned an error. Start /login again.")

    profile = _profile_from_user(result.user)
    await _sync_user(result.user.id, result.user.email)
    await pool.execute(
        """
        UPDATE device_auth_sessions
        SET status = 'authorized',
            encrypted_refresh_token = $1,
            workos_user_id = $2,
            email = $3,
            profile = $4,
            authorized_at = now(),
            error = NULL
        WHERE id = $5
        """,
        encrypt_key(result.refresh_token),
        result.user.id,
        result.user.email,
        json.dumps(profile),
        session_id,
    )

    return _device_html(
        "Terminal linked",
        "Authentication is complete. Return to the terminal and it will finish signing you in automatically.",
    )


@router.post("/token")
async def get_token(request: TokenRequest, http_request: Request):
    """Exchange device session or refresh token for local API JWTs."""
    # Handle Refresh Token Grant
    if request.grant_type == "refresh_token" and request.refresh_token:
        try:
            data = await _refresh_workos_tokens(
                refresh_token=request.refresh_token,
                ip_address=http_request.client.host if http_request.client else None,
                user_agent=http_request.headers.get("user-agent"),
            )
        except AuthenticationException:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
        except BaseRequestException as exc:
            logger.error("WorkOS refresh failed: %s", exc)
            raise HTTPException(status_code=502, detail="WorkOS token refresh failed")

        profile = _profile_from_user(data.user)
        await _sync_user(data.user.id, data.user.email)
        access_token = _generate_jwt(data.user.id, data.user.email, 3600)
        return {
            "access_token": access_token,
            "refresh_token": data.refresh_token,
            "expires_in": 3600,
            "profile": profile,
        }

    # Handle Device Code Polling
    elif request.device_code:
        pool = get_pool()
        row = await pool.fetchrow(
            """
            SELECT id, status, expires_at, encrypted_refresh_token, workos_user_id, email, profile, error
            FROM device_auth_sessions
            WHERE device_code_hash = $1
            """,
            _hash_device_code(request.device_code),
        )
        if not row:
            return _device_status_response("invalid_device_code")

        if _row_expires_at(row) <= datetime.now(timezone.utc):
            await pool.execute(
                "UPDATE device_auth_sessions SET status = 'expired', error = 'expired_token' WHERE id = $1",
                row["id"],
            )
            return _device_status_response("expired_token")

        if row["status"] == "pending":
            return _device_status_response("authorization_pending")
        if row["status"] == "failed":
            return _device_status_response(row["error"] or "access_denied")
        if row["status"] != "authorized":
            return _device_status_response("expired_token")

        encrypted_refresh_token = row["encrypted_refresh_token"]
        if not encrypted_refresh_token:
            logger.error("Authorized device session %s is missing refresh token", row["id"])
            return _device_status_response("server_error", status_code=500)

        profile = _coerce_profile(row["profile"])
        workos_user_id = row["workos_user_id"] or profile.get("id")
        email = row["email"] or profile.get("email")
        if not workos_user_id or not email:
            logger.error("Authorized device session %s is missing user identity", row["id"])
            return _device_status_response("server_error", status_code=500)

        await _sync_user(workos_user_id, email)
        access_token = _generate_jwt(workos_user_id, email, 3600)
        await pool.execute(
            """
            UPDATE device_auth_sessions
            SET status = 'consumed', consumed_at = now()
            WHERE id = $1
            """,
            row["id"],
        )
        return {
            "access_token": access_token,
            "refresh_token": decrypt_key(encrypted_refresh_token),
            "expires_in": 3600,
            "profile": profile or {"id": workos_user_id, "email": email},
        }

    else:
        raise HTTPException(status_code=400, detail="Missing grant_type or device_code")


class SSOCallbackRequest(BaseModel):
    code: str


class SigninRequest(BaseModel):
    email: str
    password: str


@router.post("/sso/callback")
async def sso_callback(request: SSOCallbackRequest, http_request: Request):
    """Exchange WorkOS SSO auth code for user profile and JWT."""
    try:
        data = await _exchange_code_for_tokens(
            code=request.code,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent"),
        )
    except AuthenticationException as exc:
        logger.warning("WorkOS SSO callback error: %s", exc)
        raise HTTPException(status_code=401, detail="SSO authentication failed")
    except BaseRequestException as exc:
        logger.error("WorkOS SSO callback error: %s", exc)
        raise HTTPException(status_code=502, detail="SSO authentication failed")

    profile = _profile_from_user(data.user)
    workos_id = data.user.id
    email = data.user.email

    if not workos_id or not email:
        raise HTTPException(status_code=400, detail="Invalid profile from WorkOS")

    await _sync_user(workos_id, email)

    access_token = _generate_jwt(workos_id, email, 3600)
    return {
        "access_token": access_token,
        "refresh_token": data.refresh_token,
        "email": email,
        "name": profile.get("name", email.split("@")[0]),
        "workos_user_id": workos_id,
        "profile": profile,
    }


@router.post("/signin")
async def signin_with_password(request: SigninRequest):
    """Email/password signin for web dashboard."""
    if not settings.allow_legacy_password_signin:
        raise HTTPException(
            status_code=403,
            detail=(
                "Email/password signin is disabled. "
                "Use WorkOS SSO login or enable ALLOW_LEGACY_PASSWORD_SIGNIN for local development."
            ),
        )

    email = request.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    if len(request.password) < 8:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    pool = get_pool()
    row = await pool.fetchrow(
        "SELECT workos_user_id, email, password_hash FROM users WHERE email = $1",
        email,
    )
    if not row:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # SECURITY: Verify password hash — reject if no hash stored or mismatch
    stored_hash = row.get("password_hash")
    if not stored_hash:
        raise HTTPException(
            status_code=401,
            detail="Password login not configured for this account. Use SSO.",
        )

    if not bcrypt.checkpw(request.password.encode("utf-8"), stored_hash.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = _generate_jwt(row["workos_user_id"], row["email"], 3600)
    return {
        "access_token": access_token,
        "email": row["email"],
        "workos_user_id": row["workos_user_id"],
    }


async def _sync_user(workos_user_id: str, email: str):
    """Upserts the WorkOS user identity into the local PostgreSQL users table."""
    pool = get_pool()
    # Check if user exists
    row = await pool.fetchrow("SELECT id FROM users WHERE workos_user_id = $1", workos_user_id)
    if not row:
        # Create new user - free tier gets ZERO credits (BYOK only)
        import asyncpg

        from src.services.analytics import track_async
        from src.services.email import email_service

        try:
            # First create a personal team for the user
            domain = email.split("@")[-1].split(".")[0].capitalize()
            team_name = f"{domain} Workspace"
            team_id = await pool.fetchval(
                """
                INSERT INTO teams (name, plan, shared_credits_remaining)
                VALUES ($1, 'free', 0)
                RETURNING id
                """,
                team_name,
            )

            await pool.execute(
                """
                INSERT INTO users (
                    workos_user_id, email, plan, credits_remaining,
                    credits_monthly, team_id, team_role, billing_access
                )
                VALUES ($1, $2, 'free', 0, 0, $3, 'owner', true)
                """,
                workos_user_id,
                email,
                team_id,
            )
            await email_service.send_welcome(email)
            await track_async(workos_user_id, "user_signed_up", {"email": email})
        except asyncpg.UniqueViolationError:
            pass  # Race condition, user already exists — safe to ignore
        except Exception as e:
            logger.error(f"Failed to sync user: {str(e)}")
            raise HTTPException(status_code=500, detail="Account creation failed")
