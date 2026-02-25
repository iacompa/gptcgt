import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.database import close_db_pool, init_db_pool
from api.middleware.auth import AuthMiddleware
from api.middleware.rate_limit import RateLimitMiddleware
from api.routes import api_keys, auth, billing, usage, users

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    await init_db_pool()
    yield
    # Shutdown actions
    await close_db_pool()


app = FastAPI(title="GPTCGT Backend API", lifespan=lifespan)

# CORS
origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Note: Starlette executes middlewares in reverse order of how they are added.
# We add RateLimitMiddleware first so it runs AFTER AuthMiddleware
# This way rate limiting runs *after* auth, giving it access to request.state.user_id.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)

# Routers
app.include_router(billing.router, prefix="/billing")
app.include_router(auth.router, prefix="/auth")
app.include_router(users.router, prefix="/user")
app.include_router(api_keys.router, prefix="/api_keys")
from fastapi.responses import JSONResponse  # noqa: E402

from src.services.monitoring import monitor  # noqa: E402


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    await monitor.log_exception(exc, {"url": str(request.url), "method": request.method})
    logger.error(f"Global exception: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(usage.router, prefix="/usage")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
