"""
API Key Validator.

Provides async methods to test if an API key is valid for a given provider
by making a minimal litellm API call (e.g. asking it to say "hello").
"""

from __future__ import annotations

import litellm

from src.core.logger import get_logger

logger = get_logger("auth.key_validator")


class KeyValidator:
    """Validates API keys against their respective providers."""

    # Map our env var names to the lightest/fastest model to test with
    # Use litellm standard naming
    TEST_MODELS = {
        "ANTHROPIC_API_KEY": "anthropic/claude-3-haiku-20240307",
        "OPENAI_API_KEY": "openai/gpt-4o-mini",
        "GEMINI_API_KEY": "google/gemini-2.5-flash",
        "DEEPSEEK_API_KEY": "deepseek/deepseek-chat",
        "XAI_API_KEY": "xai/grok-3-mini",
        "OPENROUTER_API_KEY": "openrouter/google/gemini-2.5-flash",
    }

    @classmethod
    async def validate(cls, env_var_name: str, api_key: str) -> tuple[bool, str]:
        """
        Test an API key.
        Returns (is_valid: bool, message: str)
        """
        if not api_key:
            return False, "Key is empty."

        model_id = cls.TEST_MODELS.get(env_var_name)
        if not model_id:
            # For custom keys, we don't know the endpoint easily, assume valid if present.
            return True, "Valid (Custom)"

        logger.debug(f"Testing key for {env_var_name} using {model_id}")

        messages = [{"role": "user", "content": "hello"}]

        try:
            # We use acompletion with a tiny max_tokens to minimize cost/delay
            # litellm will route this appropriately based on the prefix and passed key.
            await litellm.acompletion(
                model=model_id, messages=messages, api_key=api_key, max_tokens=5, timeout=10.0
            )
            logger.debug(f"Key validation success for {env_var_name}")
            return True, "Valid"

        except litellm.AuthenticationError as e:
            logger.warning(f"Key validation failed (Auth) for {env_var_name}: {e}")
            return False, "Invalid Key"
        except litellm.RateLimitError as e:
            # We hit rate limits, but the key *is* valid because it authenticated.
            logger.warning(f"Key validation rate limited for {env_var_name}, assuming valid: {e}")
            return True, "Valid (Rate Limited)"
        except Exception as e:
            err_str = str(e)
            if "auth" in err_str.lower() or "401" in err_str or "unauthorized" in err_str.lower():
                logger.warning(f"Key validation failed (Auth generic) for {env_var_name}: {e}")
                return False, "Invalid Key"
            # Some other error (network, down, mapping). We assume invalid so they double check,
            # or we could assume valid. Let's return the error.
            logger.error(f"Key validation error for {env_var_name}: {e}")
            return False, f"Error: {str(e)[:20]}..."
