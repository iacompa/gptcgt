import logging
from datetime import datetime, timezone
from typing import Optional

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
            await pool.execute(
                """
                INSERT INTO users (workos_user_id, email, plan, credits_remaining, credits_monthly)
                VALUES ($1, $2, 'free', 0, 0)
                """,
                workos_user_id,
                email,
            )
            await email_service.send_welcome(email)
            await track_async(workos_user_id, "user_signed_up", {"email": email})
        except asyncpg.UniqueViolationError:
            pass  # Race condition, user already exists — safe to ignore
        except Exception as e:
            logger.error(f"Failed to sync user: {str(e)}")
            raise HTTPException(status_code=500, detail="Account creation failed")
