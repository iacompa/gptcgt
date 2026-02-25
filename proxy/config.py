from pydantic_settings import BaseSettings, SettingsConfigDict

from src.services.registry import services


class ProxySettings(BaseSettings):
    """Proxy server configuration, loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    workos_api_key: str = ""
    encryption_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    allowed_ips: str = "127.0.0.1,::1"
    environment: str = "production"


proxy_settings = ProxySettings()

# Fallback to registry for values not set in environment
if not proxy_settings.database_url:
    proxy_settings.database_url = services.neon.database_url
if not proxy_settings.workos_api_key:
    proxy_settings.workos_api_key = services.workos.api_key
if not proxy_settings.encryption_key:
    proxy_settings.encryption_key = services.encryption.key
if not proxy_settings.anthropic_api_key:
    proxy_settings.anthropic_api_key = services.llm_keys.anthropic
if not proxy_settings.openai_api_key:
    proxy_settings.openai_api_key = services.llm_keys.openai
