import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.services.registry import services


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        self.redis_client = None
        if services.redis.is_configured:
            try:
                import redis.asyncio as redis
                self.redis_client = redis.from_url(services.redis.url, decode_responses=True)
            except ImportError:
                self.redis_client = None

        self.cache = {}

    async def dispatch(self, request: Request, call_next):
        # Determine the client identifier
        client_id = request.client.host
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            client_id = user_id

        if self.redis_client:
            try:
                key = f"ratelimit:{client_id}"
                count = await self.redis_client.incr(key)
                if count == 1:
                    await self.redis_client.expire(key, self.window_seconds)
                if count > self.max_requests:
                    return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})
                return await call_next(request)
            except Exception:
                pass  # Fallback to in-memory

        now = time.time()

        # Cleanup old entries (primitive background cleanup)
        if len(self.cache) > 10000:
            self.cache = {
                k: v for k, v in self.cache.items() if now - v["start_time"] < self.window_seconds
            }

        record = self.cache.get(client_id)
        if not record or now - record["start_time"] > self.window_seconds:
            self.cache[client_id] = {"count": 1, "start_time": now}
        else:
            if record["count"] >= self.max_requests:
                return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})
            record["count"] += 1

        return await call_next(request)
