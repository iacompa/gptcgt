import jwt
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from api.config import settings
from api.database import get_pool
from api.services.moderation import ModerationService

moderation_service = ModerationService()

# Paths that don't need authentication
PUBLIC_PATHS = [
    "/health",
    "/auth/device",
    "/auth/token",
    "/billing/webhook",
    "/docs",
    "/openapi.json",
]


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(p) for p in PUBLIC_PATHS):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return self._json_response(401, "Missing or invalid Authorization header")

        token = auth_header.split(" ")[1]

        # Verify JWT locally with our secret? Wait, WorkOS issues these tokens.
        # But we verify them. WorkOS uses JWKS. Let's do a basic WorkOS integration
        # or just pass through for this stub if we mock it in development.

        # In production, use standard JWKS client.
        try:
            # Verify JWT using our local secret for the MVP integration.
            # In a full production WorkOS setup, we'd use their JWKS endpoint.
            payload = jwt.decode(token, key=settings.jwt_secret, algorithms=["HS256"])
            user_id = payload.get("sub") or payload.get("id")
            if not user_id:
                return self._json_response(401, "Invalid token payload")

            request.state.user_id = user_id

            # Moderation Enforcement
            pool = get_pool()
            async with pool.acquire() as conn:
                status = await moderation_service.check_user_status(conn, user_id)
                if status["status"] != "active":
                    return self._json_response(
                        403, f"Account {status['status']}: {status.get('reason')}"
                    )

        except jwt.PyJWTError:
            return self._json_response(401, "Invalid token")

        return await call_next(request)

    def _json_response(self, status_code: int, message: str):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=status_code, content={"detail": message})
