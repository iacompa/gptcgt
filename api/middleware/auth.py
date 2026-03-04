import jwt
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from api.config import settings
from api.database import get_pool
from api.services.moderation import ModerationService
from src.auth.token_validation import verify_access_token

moderation_service = ModerationService()

# Paths that don't need authentication — EXACT match or explicit prefix
# Using tuples of (path, match_type) where match_type is "exact" or "prefix"
PUBLIC_PATHS_EXACT = frozenset({
    "/health",
    "/docs",
    "/openapi.json",
    "/auth/device",
    "/auth/token",
    "/auth/signin",
    "/auth/sso/callback",
    "/billing/webhook",
})

PUBLIC_PATH_PREFIXES = (
    "/docs/",        # Only /docs/ subpaths, not /docs-secret
    "/auth/device/",  # Only /auth/device/ subpaths
    "/auth/token/",   # Only /auth/token/ subpaths
    "/billing/webhook/",
)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # CORS preflight — always allow
        if request.method == "OPTIONS":
            return await call_next(request)

        # Public path check — exact match or explicit prefix
        if path in PUBLIC_PATHS_EXACT or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return self._json_response(401, "Missing or invalid Authorization header")

        token = auth_header.split(" ", 1)[1]

        try:
            payload = verify_access_token(
                token,
                hs256_secret=settings.jwt_secret,
                jwks_url=settings.workos_jwks_url or None,
                issuer=settings.workos_issuer or None,
                audience=settings.workos_audience or None,
            )

            user_id = payload.get("sub")
            if not user_id:
                return self._json_response(401, "Invalid token: missing subject")

            # Resolve user identity — MUST find user in DB or reject
            pool = get_pool()
            user_row = await pool.fetchrow(
                "SELECT workos_user_id FROM users WHERE workos_user_id = $1",
                user_id,
            )

            if not user_row:
                # Try matching by email (web login flow sets sub=email)
                email = payload.get("email") or user_id
                user_row = await pool.fetchrow(
                    "SELECT workos_user_id FROM users WHERE email = $1",
                    email,
                )

                if user_row:
                    user_id = user_row["workos_user_id"]
                else:
                    # SECURITY: Reject if user not found — no silent fallthrough
                    return self._json_response(
                        401,
                        "User not found. Please sign up or contact support.",
                    )

            request.state.user_id = user_id

            # Moderation Enforcement
            async with pool.acquire() as conn:
                status = await moderation_service.check_user_status(conn, user_id)
                if status["status"] != "active":
                    return self._json_response(
                        403, f"Account {status['status']}: {status.get('reason')}"
                    )

                # Credit-Exhaustion Enforcement for AI proxy endpoints
                if self._is_proxy_endpoint(path):
                    credits = await conn.fetchval(
                        """
                        SELECT COALESCE(
                            t.shared_credits_remaining,
                            u.credits_remaining,
                            0
                        )
                        FROM users u
                        LEFT JOIN teams t ON u.team_id = t.id
                        WHERE u.workos_user_id = $1
                        """,
                        user_id,
                    )
                    if credits is not None and credits <= 0:
                        msg = (
                            "⚠️ Credits exhausted. Visit your dashboard at "
                            "https://gptcgt.ai/dashboard/billing "
                            "to purchase more."
                        )
                        return self._json_response(402, msg)

        except jwt.ExpiredSignatureError:
            return self._json_response(401, "Token expired. Please sign in again.")
        except jwt.InvalidTokenError:
            return self._json_response(401, "Invalid token")

        return await call_next(request)

    def _is_proxy_endpoint(self, path: str) -> bool:
        """Check if the request targets an AI proxy endpoint."""
        # Use exact prefixes to prevent overmatching
        proxy_prefixes = ("/proxy/", "/v1/chat/", "/v1/completions")
        return any(path.startswith(p) for p in proxy_prefixes)

    def _json_response(self, status_code: int, message: str):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=status_code, content={"detail": message}
        )
