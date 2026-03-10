import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class ServiceStatus(Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    DISABLED = "disabled"


@dataclass
class ServiceConfig:
    name: str
    description: str
    status: ServiceStatus = ServiceStatus.PLANNED
    required: bool = False

    @property
    def is_configured(self) -> bool:
        """Override in subclasses to check specific env vars."""
        return False


@dataclass
class NeonConfig(ServiceConfig):
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", ""))
    pool_min: int = 2
    pool_max: int = 20

    @property
    def is_configured(self) -> bool:
        return bool(self.database_url)


@dataclass
class WorkOSConfig(ServiceConfig):
    api_key: str = field(default_factory=lambda: os.environ.get("WORKOS_API_KEY", ""))
    client_id: str = field(default_factory=lambda: os.environ.get("WORKOS_CLIENT_ID", ""))

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.client_id)


@dataclass
class StripeConfig(ServiceConfig):
    secret_key: str = field(default_factory=lambda: os.environ.get("STRIPE_SECRET_KEY", ""))
    publishable_key: str = field(default_factory=lambda: os.environ.get("STRIPE_PUBLISHABLE_KEY", ""))
    webhook_secret: str = field(default_factory=lambda: os.environ.get("STRIPE_WEBHOOK_SECRET", ""))

    price_pro_monthly: str = field(default_factory=lambda: os.environ.get("STRIPE_PRICE_PRO_MONTHLY", ""))
    price_pro_annual: str = field(default_factory=lambda: os.environ.get("STRIPE_PRICE_PRO_ANNUAL", ""))
    price_team_monthly: str = field(default_factory=lambda: os.environ.get("STRIPE_PRICE_TEAM_MONTHLY", ""))
    price_team_annual: str = field(default_factory=lambda: os.environ.get("STRIPE_PRICE_TEAM_ANNUAL", ""))
    price_enterprise: str = field(default_factory=lambda: os.environ.get("STRIPE_PRICE_ENTERPRISE", ""))

    currency: str = "usd"
    success_url: str = "https://gptcgt.ai/dashboard/billing?success=1"
    cancel_url: str = "https://gptcgt.ai/dashboard/billing?cancelled=1"
    portal_return_url: str = "https://gptcgt.ai/dashboard/billing"

    @property
    def is_configured(self) -> bool:
        return bool(self.secret_key)


@dataclass
class LLMProviderKeys(ServiceConfig):
    anthropic: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    openai: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    gemini: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))
    xai: str = field(default_factory=lambda: os.environ.get("XAI_API_KEY", ""))
    deepseek: str = field(default_factory=lambda: os.environ.get("DEEPSEEK_API_KEY", ""))
    e2b: str = field(default_factory=lambda: os.environ.get("E2B_API_KEY", ""))

    @property
    def is_configured(self) -> bool:
        return any([self.anthropic, self.openai, self.gemini, self.xai, self.deepseek, self.e2b])


@dataclass
class EncryptionConfig(ServiceConfig):
    key: str = field(default_factory=lambda: os.environ.get("ENCRYPTION_KEY", ""))

    @property
    def is_configured(self) -> bool:
        return bool(self.key and len(self.key) == 64)


@dataclass
class JWTConfig(ServiceConfig):
    secret: str = field(default_factory=lambda: os.environ.get("JWT_SECRET", ""))
    algorithm: str = "HS256"
    access_ttl: int = 3600
    refresh_ttl: int = 2592000

    @property
    def is_configured(self) -> bool:
        return bool(self.secret)


@dataclass
class ResendConfig(ServiceConfig):
    api_key: str = field(default_factory=lambda: os.environ.get("RESEND_API_KEY", ""))
    from_email: str = field(default_factory=lambda: os.environ.get("RESEND_FROM_EMAIL", "accounts@gptcgt.ai"))
    reply_to: str = field(default_factory=lambda: os.environ.get("RESEND_REPLY_TO", "support@gptcgt.ai"))

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class PostHogConfig(ServiceConfig):
    api_key: str = field(default_factory=lambda: os.environ.get("POSTHOG_API_KEY", ""))
    host: str = field(default_factory=lambda: os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com"))

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class BetterstackConfig(ServiceConfig):
    logs_token: str = field(default_factory=lambda: os.environ.get("BETTERSTACK_LOGS_TOKEN", ""))
    heartbeat_url: str = field(default_factory=lambda: os.environ.get("BETTERSTACK_HEARTBEAT_URL", ""))

    @property
    def is_configured(self) -> bool:
        return bool(self.logs_token)


@dataclass
class CloudflareR2Config(ServiceConfig):
    account_id: str = field(
        default_factory=lambda: os.environ.get("R2_ACCOUNT_ID", os.environ.get("CLOUDFLARE_R2_ACCOUNT_ID", ""))
    )
    access_key: str = field(
        default_factory=lambda: os.environ.get("R2_ACCESS_KEY", os.environ.get("CLOUDFLARE_R2_ACCESS_KEY", ""))
    )
    secret_key: str = field(
        default_factory=lambda: os.environ.get("R2_SECRET_KEY", os.environ.get("CLOUDFLARE_R2_SECRET_KEY", ""))
    )
    endpoint_url: str = field(
        default_factory=lambda: os.environ.get("R2_ENDPOINT_URL", os.environ.get("CLOUDFLARE_R2_ENDPOINT_URL", ""))
    )
    bucket: str = field(
        default_factory=lambda: os.environ.get("R2_BUCKET", os.environ.get("CLOUDFLARE_R2_BUCKET", ""))
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.account_id and self.access_key and self.secret_key)


@dataclass
class RedisConfig(ServiceConfig):
    url: str = field(default_factory=lambda: os.environ.get("REDIS_URL", ""))

    @property
    def is_configured(self) -> bool:
        return bool(self.url)


class ServiceRegistry:
    """Single source of truth for all external service configurations."""

    def __init__(self):
        self.neon = NeonConfig(name="Neon PostgreSQL", description="Primary serverless database", required=True)
        self.workos = WorkOSConfig(name="WorkOS", description="Authentication & SSO integration", required=True)
        self.stripe = StripeConfig(name="Stripe", description="Billing and subscription platform")
        self.llm_keys = LLMProviderKeys(name="LLM Providers", description="Server-side model API keys")
        self.encryption = EncryptionConfig(
            name="Encryption Vault", description="AES-256-GCM key wrapper", required=True
        )
        self.jwt = JWTConfig(name="JWT Issuer", description="Local auth token generation", required=True)

        # Planned Services
        self.resend = ResendConfig(name="Resend", description="Transactional email delivery")
        self.posthog = PostHogConfig(name="PostHog", description="Product analytics and telemetry")
        self.betterstack = BetterstackConfig(name="Betterstack", description="Uptime and log monitoring")
        self.cloudflare_r2 = CloudflareR2Config(name="Cloudflare R2", description="S3-compatible object storage")
        self.redis = RedisConfig(name="Redis", description="Caching and rate limiting")

        self.update_statuses()

    def update_statuses(self) -> None:
        """Sync configuration states with environment variables."""
        all_services = [
            self.neon,
            self.workos,
            self.stripe,
            self.llm_keys,
            self.encryption,
            self.jwt,
            self.resend,
            self.posthog,
            self.betterstack,
            self.cloudflare_r2,
            self.redis,
        ]
        for service in all_services:
            if service.is_configured:
                service.status = ServiceStatus.ACTIVE
            elif service.status != ServiceStatus.PLANNED:
                service.status = ServiceStatus.DISABLED

    def health_check(self) -> Dict[str, str]:
        """Returns the status map of all services."""
        return {
            "neon": self.neon.status.value,
            "workos": self.workos.status.value,
            "stripe": self.stripe.status.value,
            "llm_keys": self.llm_keys.status.value,
            "encryption": self.encryption.status.value,
            "jwt": self.jwt.status.value,
            "resend": self.resend.status.value,
            "posthog": self.posthog.status.value,
            "betterstack": self.betterstack.status.value,
            "cloudflare_r2": self.cloudflare_r2.status.value,
            "redis": self.redis.status.value,
        }

    def verify_required(self) -> List[str]:
        """Returns a list of names for missing required services."""
        missing = []
        if not self.neon.is_configured:
            missing.append(self.neon.name)
        if not self.workos.is_configured:
            missing.append(self.workos.name)
        if not self.encryption.is_configured:
            missing.append(self.encryption.name)
        if not self.jwt.is_configured:
            missing.append(self.jwt.name)
        return missing

    def print_status(self) -> str:
        """Human-readable status report."""
        lines = ["=== Subsystem Service Status ==="]
        for name, status in self.health_check().items():
            lines.append(f"{name.ljust(15)} : {status.upper()}")
        return "\n".join(lines)


_services = None


def __getattr__(name: str) -> ServiceRegistry:
    if name == "services":
        global _services
        if _services is None:
            _services = ServiceRegistry()
        return _services
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
