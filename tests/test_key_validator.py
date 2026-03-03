import pytest  # noqa: I001
from unittest.mock import patch, AsyncMock
import litellm

from src.auth.key_validator import KeyValidator

@pytest.mark.asyncio
async def test_validate_empty_key():
    is_valid, msg = await KeyValidator.validate("OPENAI_API_KEY", "")
    assert not is_valid
    assert "empty" in msg.lower()

@pytest.mark.asyncio
async def test_validate_custom_provider():
    is_valid, msg = await KeyValidator.validate("CUSTOM_API_KEY", "some-key")
    # Custom keys have no TEST_MODEL mapped, should return True automatically
    assert is_valid
    assert "Custom" in msg

@pytest.mark.asyncio
@patch("src.auth.key_validator.litellm.acompletion")
async def test_validate_success(mock_acompletion):
    mock_acompletion.return_value = AsyncMock()
  # noqa: W293
    is_valid, msg = await KeyValidator.validate("ANTHROPIC_API_KEY", "sk-ant-1234")
    assert is_valid
    assert msg == "Valid"
  # noqa: W293
    # Verify it used the correct light model
    mock_acompletion.assert_called_once()
    kwargs = mock_acompletion.call_args.kwargs
    assert kwargs["model"] == "anthropic/claude-3-haiku-20240307"
    assert kwargs["api_key"] == "sk-ant-1234"

@pytest.mark.asyncio
@patch("src.auth.key_validator.litellm.acompletion")
async def test_validate_auth_error(mock_acompletion):
    mock_acompletion.side_effect = litellm.AuthenticationError("Invalid API key", None, None)
  # noqa: W293
    is_valid, msg = await KeyValidator.validate("OPENAI_API_KEY", "bad-key")
    assert not is_valid
    assert msg == "Invalid Key"

@pytest.mark.asyncio
@patch("src.auth.key_validator.litellm.acompletion")
async def test_validate_rate_limit(mock_acompletion):
    # Requirement: Handle provider rate-limit as "valid but rate-limited"
    mock_acompletion.side_effect = litellm.RateLimitError("Too many requests", None, None)
  # noqa: W293
    is_valid, msg = await KeyValidator.validate("GEMINI_API_KEY", "good-key-limited")
    assert is_valid
    assert "Rate Limited" in msg

@pytest.mark.asyncio
@patch("src.auth.key_validator.litellm.acompletion")
async def test_validate_generic_auth_error_string(mock_acompletion):
    # Sometimes litellm throws generic Exception containing 401 or auth string
    mock_acompletion.side_effect = Exception("HTTP 401 Unauthorized")
  # noqa: W293
    is_valid, msg = await KeyValidator.validate("DEEPSEEK_API_KEY", "bad-key")
    assert not is_valid
    assert msg == "Invalid Key"
