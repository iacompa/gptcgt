"""
Secure OS native keychain storage for API keys.

Cross-platform: Uses OS native keychain on macOS (Keychain.app),
Windows (Credential Manager), and Linux with D-Bus/GNOME Keyring.

Headless Linux fallback: On servers/CI without a keyring daemon,
all operations gracefully fall back to environment variables so
the app works in Docker, GitHub Actions, and bare Linux installs.
"""

from __future__ import annotations

import logging
import os

import keyring
import keyring.errors

logger = logging.getLogger(__name__)

# Sentinel: set to True if we detect keyring is unavailable at runtime
_KEYRING_UNAVAILABLE = False


def _check_keyring() -> bool:
    """Return True if the OS keyring is functional. Cached after first check."""
    global _KEYRING_UNAVAILABLE
    if _KEYRING_UNAVAILABLE:
        return False
    try:
        keyring.get_password("_gptcgt_probe", "_probe")
        return True
    except Exception:
        _KEYRING_UNAVAILABLE = True
        logger.warning(
            "System keyring unavailable (headless Linux / no D-Bus session). "
            "Falling back to environment variables for API key storage. "
            "Set keys via: export OPENAI_API_KEY=... etc."
        )
        return False


class KeyChainManager:
    """
    Manages secure storage of API keys using the OS native keychain.

    On headless Linux (CI, Docker, bare servers), falls back to environment
    variables automatically so BYOK users can set: export OPENAI_API_KEY=...
    """

    SERVICE_NAME = "gptcgt"

    @classmethod
    def set_key(cls, provider: str, api_key: str) -> None:
        """Store an API key securely."""
        if _check_keyring():
            try:
                keyring.set_password(cls.SERVICE_NAME, provider, api_key)
                return
            except Exception as e:
                logger.debug(f"Keyring write failed: {e}")
        # Env-var fallback: inform the user since we can't persist
        logger.warning(f"Cannot persist {provider} to keyring. Set it via environment variable instead.")

    @classmethod
    def get_key(cls, provider: str) -> str | None:
        """Retrieve an API key — keyring first, env var fallback."""
        if _check_keyring():
            try:
                val = keyring.get_password(cls.SERVICE_NAME, provider)
                if val:
                    return val
            except Exception as e:
                logger.debug(f"Keyring read failed for {provider}: {e}")
        # Always check env var as authoritative fallback
        return os.environ.get(provider)

    @classmethod
    def clear_key(cls, provider: str) -> None:
        """Remove an API key from secure storage."""
        if _check_keyring():
            try:
                keyring.delete_password(cls.SERVICE_NAME, provider)
            except keyring.errors.PasswordDeleteError:
                pass
            except Exception as e:
                logger.debug(f"Keyring clear failed: {e}")

    @classmethod
    def has_any_keys(cls) -> bool:
        """Check if any of the major provider keys are stored."""
        for p in [
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "XAI_API_KEY",
            "DEEPSEEK_API_KEY",
            "OPENROUTER_API_KEY",
            "CUSTOM_API_KEY",
        ]:
            if cls.get_key(p):
                return True
        return False

    @classmethod
    def set_auth_tokens(cls, access: str, refresh: str) -> None:
        """Store authentication tokens securely."""
        if not _check_keyring():
            logger.warning("Cannot persist auth tokens — keyring unavailable.")
            return
        try:
            if access:
                keyring.set_password(cls.SERVICE_NAME, "GPTCGT_ACCESS_TOKEN", access)
            if refresh:
                keyring.set_password(cls.SERVICE_NAME, "GPTCGT_REFRESH_TOKEN", refresh)
        except Exception as e:
            logger.debug(f"Keyring auth token write failed: {e}")

    @classmethod
    def get_auth_tokens(cls) -> tuple[str | None, str | None]:
        """Retrieve authentication tokens securely. Returns (access_token, refresh_token)."""
        if _check_keyring():
            try:
                access = keyring.get_password(cls.SERVICE_NAME, "GPTCGT_ACCESS_TOKEN")
                refresh = keyring.get_password(cls.SERVICE_NAME, "GPTCGT_REFRESH_TOKEN")
                return access, refresh
            except Exception as e:
                logger.debug(f"Keyring auth token read failed: {e}")
        # No env-var fallback for auth tokens (they are session-specific)
        return None, None

    @classmethod
    def clear_auth_tokens(cls) -> None:
        """Remove authentication tokens from secure storage."""
        if not _check_keyring():
            return
        for key in ("GPTCGT_ACCESS_TOKEN", "GPTCGT_REFRESH_TOKEN"):
            try:
                keyring.delete_password(cls.SERVICE_NAME, key)
            except keyring.errors.PasswordDeleteError:
                pass
            except Exception as e:
                logger.debug(f"Keyring clear token failed: {e}")
