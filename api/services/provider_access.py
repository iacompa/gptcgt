from __future__ import annotations

import os
from typing import Any

from src.services.registry import services

_EXTRA_PROVIDER_ENV_MAP = {
    "cohere": "COHERE_API_KEY",
    "groq": "GROQ_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def _configured_server_provider_names() -> set[str]:
    """Return providers available from server-managed credentials."""
    configured: set[str] = set()

    llm_keys = services.llm_keys
    provider_attr_map = {
        "anthropic": "anthropic",
        "openai": "openai",
        "google": "gemini",
        "xai": "xai",
        "deepseek": "deepseek",
    }
    for provider_name, attr_name in provider_attr_map.items():
        if getattr(llm_keys, attr_name, ""):
            configured.add(provider_name)

    for provider_name, env_name in _EXTRA_PROVIDER_ENV_MAP.items():
        if os.getenv(env_name, "").strip():
            configured.add(provider_name)

    return configured


async def _fetch_user_provider_names(pool: Any, workos_user_id: str) -> set[str]:
    user_id = await pool.fetchval("SELECT id FROM users WHERE workos_user_id = $1", workos_user_id)
    if not user_id:
        return set()

    rows = await pool.fetch(
        """
        SELECT DISTINCT lower(provider) AS provider
        FROM api_keys
        WHERE owner_type = 'user' AND owner_id = $1 AND is_active = true
        """,
        user_id,
    )
    return {row["provider"] for row in rows if row["provider"]}


async def get_user_runtime_provider_profile(pool: Any, workos_user_id: str, plan: str | None = None) -> dict[str, Any]:
    """
    Resolve which model providers the current user can use from this runtime.

    Providers can come from:
    - server-managed environment credentials
    - active user-scoped BYOK entries in the encrypted api_keys table
    """
    user_providers = await _fetch_user_provider_names(pool, workos_user_id)
    server_providers = _configured_server_provider_names()
    proxy_providers = sorted(server_providers | user_providers)

    return {
        "plan": plan or "free",
        "proxy_providers": proxy_providers,
        "server_managed_providers": sorted(server_providers),
        "user_api_key_providers": sorted(user_providers),
    }
