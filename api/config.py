import os
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.endpoints import resolve_web_origin_url
from src.services.registry import services


def _default_cors_origins() -> str:
    origin = resolve_web_origin_url().rstrip("/")
    hostname = urlparse(origin).hostname or "gptcgt.ai"
    return ",".join(
        {
            origin,
            f"https://www.{hostname}",
            "https://staging.gptcgt.ai",
            "https://gptcgt-staging-web.vercel.app",
            "http://localhost:3000",
            "https://gptcgt-git-main-michaelangelor20-8162s-projects.vercel.app",
            "https://gptcgt-fv4ikb7um-michaelangelor20-8162s-projects.vercel.app",
        }
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    workos_api_key: str = ""
    workos_client_id: str = ""
    workos_jwks_url: str = ""
    workos_issuer: str = ""
    workos_audience: str = ""
    jwt_secret: str = ""
    allow_legacy_password_signin: bool = False
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    encryption_key: str = ""
    cors_origins: str = _default_cors_origins()
    environment: str = "production"

    # GitHub OAuth Settings
    github_client_id: str = ""
    github_client_secret: str = ""
    base_url: str = resolve_web_origin_url()

    # Credit Costs
    credit_cost_scout: int = 1
    credit_cost_standard: int = 5
    credit_cost_ensemble: int = 25
    credit_cost_architect: int = 100
    credit_cost_battle: int = 25
    credit_cost_sandbox: int = 1


settings = Settings()

# ── Startup validation ─────────────────────────────────────────────
_is_testing = "PYTEST_CURRENT_TEST" in os.environ or "pytest" in os.environ.get("_", "")
if settings.environment == "production" and not _is_testing:
    if not settings.jwt_secret or len(settings.jwt_secret) < 32:
        raise RuntimeError(
            "FATAL: JWT_SECRET must be at least 32 characters in production. Set the JWT_SECRET environment variable."
        )

# Fallback to registry if not loaded via env vars properly
if not settings.database_url:
    settings.database_url = services.neon.database_url
if not settings.workos_api_key:
    settings.workos_api_key = services.workos.api_key
if not settings.workos_client_id:
    settings.workos_client_id = services.workos.client_id
if not settings.workos_jwks_url and settings.workos_client_id:
    settings.workos_jwks_url = f"https://api.workos.com/sso/jwks/{settings.workos_client_id}"
if not settings.jwt_secret:
    settings.jwt_secret = services.jwt.secret
if not settings.stripe_secret_key:
    settings.stripe_secret_key = services.stripe.secret_key
if not settings.stripe_webhook_secret:
    settings.stripe_webhook_secret = services.stripe.webhook_secret
if not settings.encryption_key:
    settings.encryption_key = services.encryption.key
