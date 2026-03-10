import json
import logging
import os
import shlex
from contextlib import asynccontextmanager
from pathlib import PurePosixPath
from typing import Dict, Optional

import jwt

# Set global litellm logic up
import litellm
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from litellm import acompletion
from pydantic import BaseModel

from proxy.content_filter import ContentFilter
from proxy.database import close_db_pool, get_pool, init_db_pool
from proxy.metering import UsageMeter
from src.auth.token_validation import verify_access_token
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

    # Securely inject server keys for all supported providers
    if services.llm_keys.anthropic:
        os.environ["ANTHROPIC_API_KEY"] = services.llm_keys.anthropic
    if services.llm_keys.openai:
        os.environ["OPENAI_API_KEY"] = services.llm_keys.openai
    if getattr(services.llm_keys, "gemini", None):
        os.environ["GEMINI_API_KEY"] = services.llm_keys.gemini
    if getattr(services.llm_keys, "mistral", None):
        os.environ["MISTRAL_API_KEY"] = services.llm_keys.mistral
    if getattr(services.llm_keys, "groq", None):
        os.environ["GROQ_API_KEY"] = services.llm_keys.groq
    if getattr(services.llm_keys, "deepseek", None):
        os.environ["DEEPSEEK_API_KEY"] = services.llm_keys.deepseek
    if getattr(services.llm_keys, "e2b", None):
        os.environ["E2B_API_KEY"] = services.llm_keys.e2b

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

# ─── Security helpers ────────────────────────────────────────────────
from src.billing.credits import CreditService, resolve_billing_mode  # noqa: E402
from src.services.analytics import track_async  # noqa: E402
from src.services.monitoring import monitor  # noqa: E402

# Allowlist of safe base commands for sandbox execution
_SANDBOX_ALLOWED_COMMANDS = frozenset({
    "pytest", "python", "python3",
    "npm", "npx", "node",
    "cargo", "go", "rustc",
    "ruff", "flake8", "mypy",
    "eslint", "tsc",
    "pip", "pip3",
    "cat", "echo", "ls", "head", "tail", "wc",
})

# Ensure we do not use global sets, use local set explicitly to prevent drift


def _validate_sandbox_command(command: str) -> None:
    """
    Validate sandbox commands against an allowlist.

    Raises HTTPException if the command is not allowed.
    F04: Blocks shell metacharacters including & (backgrounding bypass).
    """
    if not command or not command.strip():
        raise HTTPException(status_code=400, detail="Empty command")

    # Check for forbidden shell metacharacters (including & for backgrounding)
    _forbidden = set(";|`$(){}\\<>!&\n\r")
    for char in command:
        if char in _forbidden:
            raise HTTPException(
                status_code=400,
                detail=f"Forbidden character in command: {char!r}",
            )

    # Check that each chained command's base binary is allowlisted.
    # Since & is now forbidden, only && chains remain impossible —
    # we validate the full command as a single unit.
    try:
        tokens = shlex.split(command)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid shell quoting in command")
    if not tokens:
        raise HTTPException(status_code=400, detail="Empty command after parsing")

    base_cmd = tokens[0]
    if base_cmd not in _SANDBOX_ALLOWED_COMMANDS:
        raise HTTPException(
            status_code=400,
            detail=f"Command not in allowlist: {base_cmd}",
        )


def _normalize_sandbox_path(rel_path: str) -> str:
    """
    Normalize user-supplied file path to a safe relative POSIX path.
    Rejects absolute paths and traversal attempts.
    """
    normalized = PurePosixPath(rel_path.strip())
    if normalized.is_absolute():
        raise HTTPException(status_code=400, detail=f"Absolute paths are not allowed: {rel_path}")
    parts = normalized.parts
    if not parts:
        raise HTTPException(status_code=400, detail="Empty file path")
    if any(part in ("..", "") for part in parts):
        raise HTTPException(status_code=400, detail=f"Invalid file path: {rel_path}")
    return str(normalized)

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
            if not secret or len(secret) < 32:
                raise ValueError("JWT_SECRET missing or too short (must be ≥32 chars)")
            payload = verify_access_token(
                token,
                hs256_secret=secret,
                jwks_url=os.environ.get("WORKOS_JWKS_URL") or None,
                issuer=os.environ.get("WORKOS_ISSUER") or "gptcgt",
                audience=os.environ.get("WORKOS_AUDIENCE") or "gptcgt-api",
            )
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
    allowed, reason = content_filter.map_messages(messages, user_id=user_id)
    if not allowed:
        logger.warning(f"Blocked request from {user_id} due to content policy: {reason}")
        raise HTTPException(status_code=403, detail="Request blocked by content filter.")

    pool = get_pool()
    # SECURITY: Determine mode server-side from the model name.
    # Client-controlled X-GPTCGT-Mode was a billing fraud vector.
    mode = resolve_billing_mode(model)

    # 2. Spending Cap Check
    cost = credit_service.CREDIT_COSTS.get(mode, 5)
    preflight = await credit_service.check_credits(pool, user_id, mode)
    if not preflight["can_proceed"]:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Requires {preflight.get('credits_cost', cost)}. Remaining: {preflight.get('remaining', 0)}",  # noqa: E501
        )

    cap_status = await spending_caps.check_before_task(pool, user_id, cost)
    if not cap_status["allowed"]:
        raise HTTPException(
            status_code=403,
            detail=f"Spending cap exceeded. Reason: {cap_status['reason']}. Spent: ${cap_status['spent_dollars']}",  # noqa: E501
        )

    # 3. Atomic Credit Check & Deduct
    affordability = await credit_service.check_and_deduct(pool, user_id, mode)
    if not affordability["can_proceed"]:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Requires {affordability.get('credits_cost', cost)}. Remaining: {affordability.get('remaining', 0)}",  # noqa: E501
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
        refund = await credit_service.refund_fixed(pool, user_id, affordability["credits_cost"])
        if not refund.get("success"):
            logger.error(f"Failed to refund credits after upstream error for {user_id}: {refund}")
        raise HTTPException(status_code=502, detail=f"Upstream provider error: {str(e)}")


@app.get("/health")
async def proxy_health():
    try:
        pool = get_pool()
        await pool.fetchval("SELECT 1")
    except Exception:
        raise HTTPException(status_code=503, detail="Database connection failed")

    return {"status": "ok", "litellm_version": litellm.__version__}



class SandboxExecuteRequest(BaseModel):
    files: Dict[str, str]
    language: str
    command: Optional[str] = None

@app.post("/v1/sandbox/execute")
async def proxy_sandbox_execute(request_data: SandboxExecuteRequest, user_id: str = Depends(verify_proxy_auth)):
    e2b_key = os.environ.get("E2B_API_KEY")
    if not e2b_key:
        raise HTTPException(status_code=503, detail="E2B Sandbox not configured on proxy server")

    # 1. Prevent Abuse: Payload Size Limit (Max 2MB total files)
    total_size = sum(len(content) for content in request_data.files.values())
    if total_size > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Payload too large (max 2MB)")

    pool = get_pool()
    mode = "sandbox"
    cost = 1  # 1 credit (~$0.001) per sandbox run

    # 2. Credit preflight
    preflight = await credit_service.check_credits(pool, user_id, mode)
    if not preflight["can_proceed"]:
        raise HTTPException(status_code=402, detail="Insufficient credits for sandbox execution")

    # 3. Spending Cap Check
    cap_status = await spending_caps.check_before_task(pool, user_id, cost)
    if not cap_status["allowed"]:
        raise HTTPException(status_code=403, detail="Spending cap exceeded")

    try:
        from e2b_code_interpreter import Sandbox
    except ImportError:
        raise HTTPException(status_code=503, detail="e2b_code_interpreter missing on server")

    template_map = {
        "python": "python-3.11",
        "javascript": "node-18",
        "typescript": "node-18",
        "go": "go-1.21",
        "rust": "rust-1.75",
    }
    template = template_map.get(request_data.language.lower(), "python-3.11")

    # 4. Zero-Retention Execution
    try:
        sandbox = Sandbox(api_key=e2b_key, template=template)
    except Exception as e:
        logger.error(f"Failed to provision E2B sandbox: {e}")
        raise HTTPException(status_code=502, detail="Sandbox provisioning failed")

    try:
        # Write files entirely in-memory to the E2B VM
        for rel_path, content in request_data.files.items():
            safe_rel_path = _normalize_sandbox_path(rel_path)
            sandbox.files.write(f"/home/user/project/{safe_rel_path}", content)

        if not request_data.command:
            raise HTTPException(status_code=400, detail="Command is required")

        # SECURITY: Validate command against allowlist to prevent injection
        _validate_sandbox_command(request_data.command)

        result = sandbox.commands.run(
            request_data.command,
            cwd="/home/user/project",
            timeout=45
        )

        deduction = await credit_service.deduct_fixed(pool, user_id, cost)
        if not deduction.get("success"):
            raise HTTPException(status_code=402, detail="Unable to finalize sandbox billing")

        # 5. Record successful usage after billing succeeds
        meter = UsageMeter(mode=mode, workos_user_id=user_id, cost_credits=cost)
        await meter.record_fixed_cost("e2b_sandbox_run")

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Execution error in sandbox: {e}")
        raise HTTPException(status_code=500, detail="Sandbox execution failed temporarily. Please try again.")
    finally:
        # 6. Immediate Cleanup
        try:
            sandbox.kill()
        except Exception:
            pass
