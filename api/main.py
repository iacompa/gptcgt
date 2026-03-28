import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.database import close_db_pool, init_db_pool
from api.middleware.auth import AuthMiddleware
from api.middleware.rate_limit import RateLimitMiddleware
from api.routes import api_keys, auth, billing, github, hub, models, proxy, team, team_invites, usage, users
from src.services.registry import services
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")


from api.workers.deduction_worker import process_deductions_loop  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    await init_db_pool()
    worker_task = asyncio.create_task(process_deductions_loop())
    yield
    # Shutdown actions
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    await close_db_pool()


app = FastAPI(title="GPTCGT Backend API", lifespan=lifespan)

# Middleware execution order in Starlette: LAST added = FIRST to run.
# CORSMiddleware MUST run first so that ALL responses (including 401s from AuthMiddleware)
# get proper CORS headers. Without this, the browser blocks error responses as CORS violations.
origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(billing.router, prefix="/billing")
app.include_router(auth.router, prefix="/auth")
app.include_router(users.router, prefix="/user")
app.include_router(team.router, prefix="/team")
app.include_router(team_invites.router, prefix="/team/invites")
app.include_router(api_keys.router, prefix="/api_keys")
app.include_router(github.router, prefix="/github")
from fastapi.responses import JSONResponse  # noqa: E402

from src.services.monitoring import monitor  # noqa: E402


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    await monitor.log_exception(exc, {"url": str(request.url), "method": request.method})
    logger.error(f"Global exception: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(usage.router, prefix="/usage")
app.include_router(models.router, prefix="/models")
app.include_router(proxy.router, prefix="/proxy")
app.include_router(hub.router, prefix="/hub")


@app.get("/health")
async def health_check():
    required_missing = services.verify_required()
    missing_billing = []
    require_stripe = os.getenv("REQUIRE_STRIPE", "true").lower() != "false"
    if require_stripe:
        if not services.stripe.is_configured:
            missing_billing.append("stripe")
        elif not services.stripe.webhook_secret:
            missing_billing.append("stripe_webhook_secret")

    if missing_billing:
        required_missing.extend([item for item in missing_billing if item not in required_missing])

    status = "ok" if not required_missing else "degraded"

    return {
        "status": status,
        "environment": settings.environment,
        "required_services_missing": required_missing,
        "requires_billing": require_stripe,
        "services": services.health_check(),
    }
