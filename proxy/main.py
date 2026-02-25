import json
import logging
import os
from contextlib import asynccontextmanager

import jwt

# Set global litellm logic up
import litellm
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from litellm import acompletion

from proxy.content_filter import ContentFilter
from proxy.database import close_db_pool, get_pool, init_db_pool
from proxy.metering import UsageMeter
from src.billing.credits import CreditService
from src.billing.spending_caps import SpendingCapService
from src.services.registry import services

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("proxy")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not services.jwt.secret or len(services.jwt.secret) < 32:
        logger.fatal("Invalid or missing JWT secret! Must be at least 32 chars securely generated.")
        import sys

        sys.exit(1)

    # Securely inject server keys
    if services.llm_keys.anthropic:
        os.environ["ANTHROPIC_API_KEY"] = services.llm_keys.anthropic
    if services.llm_keys.openai:
        os.environ["OPENAI_API_KEY"] = services.llm_keys.openai

    # Startup actions
    await init_db_pool()
    yield
    # Shutdown actions
    await close_db_pool()


app = FastAPI(title="GPTCGT LiteLLM Proxy", lifespan=lifespan)

content_filter = ContentFilter()
credit_service = CreditService()
spending_caps = SpendingCapService()

from fastapi.responses import JSONResponse  # noqa: E402

from src.services.analytics import track_async  # noqa: E402
from src.services.monitoring import monitor  # noqa: E402


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    await monitor.log_exception(exc, {"url": str(request.url), "method": request.method})
    logger.error(f"Global exception: {exc}")
    # Don't silence validation errors
    if isinstance(exc, HTTPException):
        raise exc
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


async def verify_proxy_auth(request: Request) -> str:
    """Extract and verify WorkOS user_id from the proxy request headers."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Bearer token")

    token = auth_header.replace("Bearer ", "")
    if token.startswith("sk-gptcgt-"):
        # Real API Key Flow - O(1) Hash Lookup
        pool = get_pool()
        try:
            import hashlib

            key_hash = hashlib.sha256(token.encode()).hexdigest()

            owner_id = await pool.fetchval(
                "SELECT owner_id FROM api_keys WHERE is_active = true AND owner_type = 'user' AND key_hash = $1",  # noqa: E501
                key_hash,
            )

            if owner_id:
                workos_id = await pool.fetchval(
                    "SELECT workos_user_id FROM users WHERE id = $1", owner_id
                )
                if workos_id:
                    return workos_id

            raise HTTPException(status_code=401, detail="Invalid API Key")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"API Key validation system error: {e}")
            raise HTTPException(status_code=500, detail="Internal Auth Error")
    else:
        # JWT Flow
        try:
            secret = services.jwt.secret
            if not secret:
                raise ValueError("JWT_SECRET missing")
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            return payload["sub"]
        except jwt.PyJWTError as e:
            logger.warning(f"JWT Validation failed: {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid token")


@app.post("/v1/chat/completions")
async def proxy_completions(request: Request, user_id: str = Depends(verify_proxy_auth)):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    model = body.get("model")
    messages = body.get("messages", [])
    stream = body.get("stream", False)

    # 1. Content Filtering
    allowed, reason = content_filter.map_messages(messages)
    if not allowed:
        logger.warning(f"Blocked request from {user_id} due to content policy: {reason}")
        raise HTTPException(status_code=403, detail="Request blocked by content filter.")

    pool = get_pool()
    mode = request.headers.get("X-GPTCGT-Mode", "standard")

    # 2. Credit Check
    affordability = await credit_service.check_credits(pool, user_id, mode)
    if not affordability["can_proceed"]:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Requires {affordability['credits_cost']}. Remaining: {affordability['remaining']}",  # noqa: E501
        )

    # 3. Spending Cap Check
    cap_status = await spending_caps.check_before_task(pool, user_id, affordability["credits_cost"])
    if not cap_status["allowed"]:
        raise HTTPException(
            status_code=403,
            detail=f"Spending cap exceeded. Reason: {cap_status['reason']}. Spent: ${cap_status['spent_dollars']}",  # noqa: E501
        )

    # Prepare LiteLLM injection
    litellm_args = body.copy()

    # Create usage meter
    meter = UsageMeter(
        mode=mode, workos_user_id=user_id, cost_credits=affordability["credits_cost"]
    )

    try:
        if stream:
            response = await acompletion(**litellm_args)
            await track_async(
                user_id, "proxy_request", {"model": model, "mode": mode, "stream": True}
            )
            return StreamingResponse(
                meter.stream_and_meter(response), media_type="text/event-stream"
            )
        else:
            response = await acompletion(**litellm_args)
            await meter.finalize_non_stream(response)
            await track_async(
                user_id, "proxy_request", {"model": model, "mode": mode, "stream": False}
            )
            return response.model_dump()

    except Exception as e:
        logger.error(f"LiteLLM Error: {e}")
        raise HTTPException(status_code=502, detail=f"Upstream provider error: {str(e)}")


@app.get("/health")
async def proxy_health():
    try:
        pool = get_pool()
        await pool.fetchval("SELECT 1")
    except Exception:
        raise HTTPException(status_code=503, detail="Database connection failed")

    return {"status": "ok", "litellm_version": litellm.__version__}
