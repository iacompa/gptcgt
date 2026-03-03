from pydantic_settings import BaseSettings, SettingsConfigDict

from src.services.registry import services


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    workos_api_key: str = ""
    workos_client_id: str = ""
    jwt_secret: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    encryption_key: str = ""
    cors_origins: str = "https://gptcgt.ai,https://www.gptcgt.ai,http://localhost:3000,https://gptcgt-git-main-michaelangelor20-8162s-projects.vercel.app,https://gptcgt-fv4ikb7um-michaelangelor20-8162s-projects.vercel.app"
    environment: str = "production"


settings = Settings()

# Fallback to registry if not loaded via env vars properly
if not settings.database_url:
    settings.database_url = services.neon.database_url
if not settings.workos_api_key:
    settings.workos_api_key = services.workos.api_key
if not settings.workos_client_id:
    settings.workos_client_id = services.workos.client_id
if not settings.jwt_secret:
    settings.jwt_secret = services.jwt.secret
if not settings.stripe_secret_key:
    settings.stripe_secret_key = services.stripe.secret_key
if not settings.stripe_webhook_secret:
    settings.stripe_webhook_secret = services.stripe.webhook_secret
if not settings.encryption_key:
    settings.encryption_key = services.encryption.key
