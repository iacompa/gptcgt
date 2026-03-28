"""Shared endpoint resolution for terminal and backend integrations."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit


_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "endpoints.defaults.json"


def _load_defaults() -> dict[str, str]:
    """Load canonical defaults from the shared config JSON file."""
    try:
        with _CONFIG_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
            return {
                key: str(value).strip()
                for key, value in data.items()
                if isinstance(value, str) and value.strip()
            }
    except Exception:
        return {
            "DEFAULT_BACKEND_API_URL": "https://gptcgt-api.fly.dev",
            "DEFAULT_API_URL": "http://127.0.0.1:8000",
            "DEFAULT_SANDBOX_API_URL": "https://gptcgt.ai/api",
            "DEFAULT_BASE_URL": "https://gptcgt.ai",
            "DEFAULT_WEB_ORIGIN": "https://gptcgt.ai",
            "DEFAULT_PROXY_PATH": "proxy/v1",
        }


_DEFAULTS = _load_defaults()


DEFAULT_BACKEND_API_URL = _DEFAULTS["DEFAULT_BACKEND_API_URL"]
DEFAULT_API_URL = _DEFAULTS["DEFAULT_API_URL"]
DEFAULT_SANDBOX_API_URL = _DEFAULTS["DEFAULT_SANDBOX_API_URL"]
DEFAULT_BASE_URL = _DEFAULTS["DEFAULT_BASE_URL"]
DEFAULT_WEB_ORIGIN = _DEFAULTS["DEFAULT_WEB_ORIGIN"]
PROXY_PATH = _DEFAULTS["DEFAULT_PROXY_PATH"].strip("/")

CHAT_COMPLETION_PATH = "chat/completions"
SANDBOX_EXECUTE_PATH = "v1/sandbox/execute"


def _normalize(url: str | None) -> str:
    """Trim whitespace and trim trailing slashes so joins are predictable."""
    if not url:
        return ""
    return url.strip().rstrip("/")


def _env(env: dict[str, str] | None, key: str) -> str | None:
    if not env:
        env = os.environ
    value = env.get(key)
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return None


def resolve_web_origin_url(
    env: dict[str, str] | None = None,
    fallback: str = DEFAULT_WEB_ORIGIN,
) -> str:
    """Resolve web origin (used by redirect/callback URLs and UI links)."""
    resolved = (
        _env(env, "GPTCGT_WEB_ORIGIN")
        or _env(env, "GPTCGT_BASE_URL")
        or _env(env, "PUBLIC_BASE_URL")
        or _env(env, "PUBLIC_WEB_ORIGIN")
        or _env(env, "NEXT_PUBLIC_BASE_URL")
        or _env(env, "BASE_URL")
        or _env(env, "AUTH_CALLBACK_ORIGIN")
        or _env(env, "WEB_ORIGIN")
        or fallback
    )
    return _normalize(resolved)


def resolve_public_api_url(
    env: dict[str, str] | None = None,
    fallback: str = DEFAULT_API_URL,
) -> str:
    """Resolve public API base URL used by browser-facing clients."""
    resolved = (
        _env(env, "NEXT_PUBLIC_API_URL")
        or _env(env, "API_URL")
        or _env(env, "PUBLIC_API_URL")
        or _env(env, "PUBLIC_BASE_URL")
        or _env(env, "GPTCGT_API_BASE_URL")
        or fallback
    )
    return _normalize(resolved)


def resolve_terminal_api_base_url(
    base_url: str | None = None,
    env: dict[str, str] | None = None,
    fallback: str = DEFAULT_BACKEND_API_URL,
) -> str:
    """
    Resolve the base URL for terminal-authenticated backend calls.

    Preference order intentionally mirrors web backend config precedence:
    - explicit base_url argument
    - GPTCGT_API_BASE_URL (explicit terminal override)
    - API_URL
    - NEXT_PUBLIC_API_URL
    - PUBLIC_API_URL
    """
    resolved = (
        _normalize(base_url)
        or _env(env, "GPTCGT_API_BASE_URL")
        or _env(env, "GPTCGT_BACKEND_API_URL")
        or _env(env, "API_URL")
        or _env(env, "NEXT_PUBLIC_API_URL")
        or _env(env, "PUBLIC_API_URL")
        or fallback
    )
    return _normalize(resolved)


def resolve_terminal_proxy_url(base_url: str | None = None, env: dict[str, str] | None = None) -> str:
    """Resolve terminal proxy base URL (e.g. https://.../proxy/v1)."""
    resolved_base = _normalize(base_url) or resolve_terminal_api_base_url(env=env)
    return f"{resolved_base}/{PROXY_PATH}"


def resolve_chat_completion_url(base_url: str | None = None, env: dict[str, str] | None = None) -> str:
    """Resolve terminal chat completion endpoint URL."""
    return f"{resolve_terminal_proxy_url(base_url=base_url, env=env)}/{CHAT_COMPLETION_PATH}"


def resolve_sandbox_api_url(
    explicit: str | None = None, env: dict[str, str] | None = None, fallback: str = DEFAULT_SANDBOX_API_URL
) -> str:
    """Resolve the /api proxy base URL used for zero-retention sandbox verification."""
    resolved = (
        explicit
        or _env(env, "GPTCGT_SANDBOX_API_BASE_URL")
        or _env(env, "GPTCGT_SANDBOX_BASE_URL")
        or fallback
    )
    return _normalize(resolved)


def resolve_sandbox_execute_url(
    explicit: str | None = None, env: dict[str, str] | None = None, fallback: str = DEFAULT_SANDBOX_API_URL
) -> str:
    """Resolve /v1/sandbox/execute endpoint for verified server-side code execution."""
    base = resolve_sandbox_api_url(explicit=explicit, env=env, fallback=fallback)
    if base:
        return f"{base}/{SANDBOX_EXECUTE_PATH}"
    return SANDBOX_EXECUTE_PATH


def validate_http_url(url: str) -> bool:
    """Simple URL sanity check for configured endpoints."""
    parsed = urlsplit(_normalize(url))
    return bool(parsed.scheme in ("http", "https") and parsed.netloc)
