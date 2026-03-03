import pytest  # noqa: I001
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.chat_pipeline import ChatPipeline
from src.core.model_registry import ModelDefinition, ModelRegistry, Provider
from src.core.config import ConfigManager

@pytest.fixture
def mock_registry():
    registry = ModelRegistry()
    yield registry

@pytest.fixture
def mock_config():
    cm = ConfigManager()
    cm.user.custom_models = []
    yield cm

@pytest.mark.asyncio
async def test_custom_model_no_api_key_required(mock_registry):
    """Test that a CUSTOM model with api_key_required=False passes credential resolution."""
    model_def = ModelDefinition(
        id="custom/local-llm",
        name="Local",
        provider=Provider.CUSTOM,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
        max_context_tokens=8000,
        base_url="http://localhost:8080/v1",
        api_key_required=False
    )
  # noqa: W293
    pipeline = ChatPipeline(chat_store=MagicMock())
    error_cb = AsyncMock()
  # noqa: W293
    with patch("src.auth.keychain.KeyChainManager.get_key", return_value=None):
        from src.agents.factory import PROVIDER_KEY_MAP
        from src.auth.keychain import KeyChainManager
        api_key, base_url = await pipeline._resolve_api_credentials(
            model_def, KeyChainManager, PROVIDER_KEY_MAP, error_cb
        )
  # noqa: W293
    assert api_key is None
    assert base_url == "http://localhost:8080/v1"
    error_cb.assert_not_called()

@pytest.mark.asyncio
async def test_custom_model_api_key_required_but_missing(mock_registry):
    """Test that a CUSTOM model requiring a key fails gracefully if missing."""
    model_def = ModelDefinition(
        id="custom/secure-llm",
        name="Secure",
        provider=Provider.CUSTOM,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
        max_context_tokens=8000,
        base_url="https://secure.endpoint/v1",
        api_key_required=True
    )
  # noqa: W293
    pipeline = ChatPipeline(chat_store=MagicMock())
    error_cb = AsyncMock()
  # noqa: W293
    with patch("src.auth.keychain.KeyChainManager.get_key", return_value=None):
        from src.agents.factory import PROVIDER_KEY_MAP
        from src.auth.keychain import KeyChainManager
        api_key, base_url = await pipeline._resolve_api_credentials(
            model_def, KeyChainManager, PROVIDER_KEY_MAP, error_cb
        )
  # noqa: W293
    assert api_key is None
    assert base_url is None
    error_cb.assert_called_once()
    assert "Missing API key for custom endpoint" in error_cb.call_args[0][0]
  # noqa: W293
@pytest.mark.asyncio
async def test_custom_model_invalid_base_url():
    """Test that a malformed base_url triggers an error."""
    model_def = ModelDefinition(
        id="custom/bad-url",
        name="Bad",
        provider=Provider.CUSTOM,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
        max_context_tokens=8000,
        base_url="not-a-url",
        api_key_required=False
    )
  # noqa: W293
    pipeline = ChatPipeline(chat_store=MagicMock())
    error_cb = AsyncMock()
  # noqa: W293
    with patch("src.auth.keychain.KeyChainManager.get_key", return_value=None):
        from src.agents.factory import PROVIDER_KEY_MAP
        from src.auth.keychain import KeyChainManager
        api_key, base_url = await pipeline._resolve_api_credentials(
            model_def, KeyChainManager, PROVIDER_KEY_MAP, error_cb
        )
  # noqa: W293
    assert api_key is None
    assert base_url is None
    error_cb.assert_called_once()
    assert "Invalid custom base_url" in error_cb.call_args[0][0]

def test_config_loads_custom_models(mock_config, mock_registry):
    """Test that custom models persist through config and load into registry."""
    custom_model_dict = {
        "id": "custom/my-local",
        "name": "My Local",
        "provider": "custom",
        "input_cost_per_mtok": 0.0,
        "output_cost_per_mtok": 0.0,
        "max_context_tokens": 16000,
        "base_url": "http://127.0.0.1:1234/v1",
        "api_key_required": False
    }
  # noqa: W293
    # Simulate loading into config
    mock_registry.load(custom_models=[custom_model_dict])
  # noqa: W293
    loaded_model = mock_registry.get("custom/my-local")
    assert loaded_model is not None
    assert loaded_model.provider == Provider.CUSTOM
    assert loaded_model.base_url == "http://127.0.0.1:1234/v1"
    assert loaded_model.api_key_required is False
