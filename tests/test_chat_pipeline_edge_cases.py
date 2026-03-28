from pathlib import Path

import pytest

from src.auth.keychain import KeyChainManager
from src.core.chat_pipeline import ChatPipeline
from src.core.chat_store import ChatStore
from src.core.model_registry import ModelDefinition, Provider, QualityTier


class MockWorkspace:
    def __init__(self, path: Path):
        self._path = path

    def get_project_root(self) -> Path:
        return self._path


@pytest.fixture
def mock_store(tmp_path):
    ws = MockWorkspace(tmp_path)
    store = ChatStore(ws)
    store.new_session()
    return store


def _model(*, provider: Provider, model_id: str, base_url: str | None = None, api_key_required: bool = True):
    return ModelDefinition(
        id=model_id,
        name=model_id,
        provider=provider,
        input_cost_per_mtok=1.0,
        output_cost_per_mtok=1.0,
        max_context_tokens=128_000,
        api_key_required=api_key_required,
        base_url=base_url,
    )


@pytest.mark.asyncio
async def test_resolve_api_credentials_rejects_invalid_custom_base_url(monkeypatch, mock_store):
    model = _model(provider=Provider.OPENAI, model_id="openai/gpt-4o-mini", base_url="not-a-valid-url")
    pipeline = ChatPipeline(mock_store, default_tier=QualityTier.STANDARD)
    errors: list[str] = []

    monkeypatch.setattr(KeyChainManager, "get_key", lambda *_: "key-123")

    api_key, resolved_base_url = await pipeline._resolve_api_credentials(
        model,
        KeyChainManager,
        None,
        lambda message: errors.append(message),
    )

    assert api_key is None
    assert resolved_base_url is None
    assert errors == [
        "Invalid custom base_url: 'not-a-valid-url'. Must include valid scheme (http/https) and host."
    ]


@pytest.mark.asyncio
async def test_resolve_api_credentials_allows_custom_model_without_api_key(monkeypatch, mock_store):
    model = _model(
        provider=Provider.CUSTOM,
        model_id="custom/local-proxy",
        base_url="https://custom.local/v1",
        api_key_required=False,
    )
    pipeline = ChatPipeline(mock_store, default_tier=QualityTier.STANDARD)
    errors: list[str] = []

    monkeypatch.setattr(KeyChainManager, "get_key", lambda *_: None)

    api_key, resolved_base_url = await pipeline._resolve_api_credentials(
        model,
        KeyChainManager,
        None,
        lambda message: errors.append(message),
    )

    assert api_key is None
    assert resolved_base_url == "https://custom.local/v1"
    assert not errors
