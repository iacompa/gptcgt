import logging
from datetime import datetime, timezone
from typing import Optional

import bcrypt
import httpx
import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.config import settings
from api.database import get_pool

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"])


def _generate_jwt(sub: str, email: str, ttl: int = 3600) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "iss": "gptcgt",
        "aud": "gptcgt-api",
        "iat": now.timestamp(),
        "exp": now.timestamp() + ttl,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


class TokenRequest(BaseModel):
    client_id: Optional[str] = None
    device_code: Optional[str] = None
    grant_type: Optional[str] = None
    refresh_token: Optional[str] = None


@router.post("/device")
async def start_device_flow(client_id: Optional[str] = None):
    """Initiates device authorization flow."""
    resolved_client_id = client_id or settings.workos_client_id
    if not resolved_client_id:
        raise HTTPException(status_code=400, detail="Missing client_id in request or server config")

    url = "https://api.workos.com/sso/authorize_device"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, data={"client_id": resolved_client_id})

        if resp.status_code != 200:
            logger.error(f"WorkOS Error: {resp.text}")
            raise HTTPException(status_code=500, detail="Failed to initiate device flow")

        return resp.json()


@router.post("/token")
async def get_token(request: TokenRequest):
    """Exchange device code or refresh token for JWT tokens."""
    # Handle Refresh Token Grant
    if request.grant_type == "refresh_token" and request.refresh_token:
        url = "https://api.workos.com/sso/token"
        async with httpx.AsyncClient() as httpx_client:
            resp = await httpx_client.post(
                url,
                data={
                    "client_id": settings.workos_client_id,
                    "client_secret": settings.workos_api_key,
                    "grant_type": "refresh_token",
                    "refresh_token": request.refresh_token,
                },
            )

            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

            data = resp.json()
            profile = data.get("profile", {})

            # Issue local JWT
            access_token = _generate_jwt(profile.get("id"), profile.get("email"), 3600)
            return {
                "access_token": access_token,
                "refresh_token": data.get("refresh_token"),
                "expires_in": 3600,
                "profile": profile,
            }

    # Handle Device Code Polling
    elif request.device_code:
        if not request.device_code:
            raise HTTPException(status_code=400, detail={"error": "missing_device_code"})

        url = "https://api.workos.com/sso/token"
        async with httpx.AsyncClient() as httpx_client:
            resp = await httpx_client.post(
                url,
                data={
                    "client_id": request.client_id,
                    "client_secret": settings.workos_api_key,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": request.device_code,
                },
            )

            if resp.status_code == 400:
                data = resp.json()
                if data.get("error") == "authorization_pending":
                    raise HTTPException(status_code=400, detail={"error": "authorization_pending"})
                raise HTTPException(status_code=400, detail=data)

            resp.raise_for_status()
            data = resp.json()
            profile = data.get("profile", {})

            # Sync user to local DB
            await _sync_user(profile.get("id"), profile.get("email"))

            # Return local JWT wrapped securely
            access_token = _generate_jwt(profile.get("id"), profile.get("email"), 3600)
            return {
                "access_token": access_token,
                "refresh_token": data.get("refresh_token"),
                "expires_in": 3600,
                "profile": profile,
            }

    else:
        raise HTTPException(status_code=400, detail="Missing grant_type or device_code")


class SSOCallbackRequest(BaseModel):
    code: str


class SigninRequest(BaseModel):
    email: str
    password: str


@router.post("/sso/callback")
async def sso_callback(request: SSOCallbackRequest):
    """Exchange WorkOS SSO auth code for user profile and JWT."""
    url = "https://api.workos.com/sso/token"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            data={
                "client_id": settings.workos_client_id,
                "client_secret": settings.workos_api_key,
                "grant_type": "authorization_code",
                "code": request.code,
            },
        )

        if resp.status_code != 200:
            logger.error(f"SSO callback error: {resp.text}")
            raise HTTPException(status_code=401, detail="SSO authentication failed")

        data = resp.json()
        profile = data.get("profile", {})
        workos_id = profile.get("id")
        email = profile.get("email")

        if not workos_id or not email:
            raise HTTPException(status_code=400, detail="Invalid profile from WorkOS")

        await _sync_user(workos_id, email)

        access_token = _generate_jwt(workos_id, email, 3600)
        return {
            "access_token": access_token,
            "email": email,
            "name": profile.get("first_name", email.split("@")[0]),
            "workos_user_id": workos_id,
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
