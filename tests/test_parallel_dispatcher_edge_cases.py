from types import SimpleNamespace

import pytest

from src.core.model_registry import ModelDefinition, Provider
from src.core.parallel_dispatcher import ParallelDispatcher


def _model(model_id: str) -> ModelDefinition:
    return ModelDefinition(
        id=model_id,
        name=model_id,
        provider=Provider.OPENAI,
        input_cost_per_mtok=1.0,
        output_cost_per_mtok=1.0,
        max_context_tokens=128_000,
    )


@pytest.mark.asyncio
async def test_dispatch_errors_when_keyless_models_are_insufficient(monkeypatch):
    monkeypatch.setattr("src.core.parallel_dispatcher.KeyChainManager.get_key", lambda *_: None)

    events = []
    async for event in ParallelDispatcher().dispatch("hello", [], [_model("openai/gpt-4o-mini")], []):
        events.append(event)

    assert events == [{"type": "error", "error": "Need at least 2 runnable models for parallel mode"}]


@pytest.mark.asyncio
async def test_dispatch_errors_when_managed_mode_is_missing_tokens(monkeypatch):
    class FakeAuthManager:
        use_managed_credits = True

    class FakeApp(SimpleNamespace):
        auth_manager = FakeAuthManager()

    monkeypatch.setattr(
        "textual.app.active_app",
        SimpleNamespace(get=lambda: FakeApp()),
        raising=False,
    )
    monkeypatch.setattr("src.core.parallel_dispatcher.KeyChainManager.get_auth_tokens", lambda: (None, None))

    events = []
    models = [
        _model("openai/gpt-4o-mini"),
        _model("openai/gpt-4o"),
    ]
    async for event in ParallelDispatcher().dispatch("hello", [], models, []):
        events.append(event)

    assert events == [
        {
            "type": "error",
            "error": "Authentication token missing for managed credits. Please sign in again.",
        }
    ]
