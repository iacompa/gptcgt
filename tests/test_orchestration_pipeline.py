"""
Integration test for the full orchestration pipeline.

Tests the sequence: Router → ChatPipeline → model resolution → error handling,
plus the new ELO feedback loop and ContextTruncated event path.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.chat_pipeline import ChatPipeline
from src.core.chat_store import ChatStore
from src.core.events import ContextTruncated, ReflectionRetryHint
from src.core.model_registry import QualityTier
from src.core.router import CodingRouter


class MockWorkspace:
    def get_project_root(self):
        return Path("/tmp/mock_workspace")


@pytest.fixture
def mock_store(tmp_path):
    ws = MockWorkspace()
    ws.get_project_root = lambda: tmp_path
    store = ChatStore(ws)
    store.new_session()
    return store


@pytest.fixture
def mock_router(tmp_path):
    """Router with no real ELO data — falls back to cost sort."""
    with patch("src.core.router.Workspace") as MockWS:
        MockWS.get_instance.return_value = MagicMock(
            get_project_root=lambda: tmp_path
        )
        router = CodingRouter()
    return router


# ---------------------------------------------------------------------------
# Router tests
# ---------------------------------------------------------------------------


def test_router_raises_when_no_models(mock_router):
    """route_task must raise ValueError (not return None) when no models available."""
    with patch.object(mock_router.registry, "get_available_models", return_value=[]):
        with patch.object(mock_router.registry, "get_all", return_value=[]):
            with pytest.raises(ValueError, match="No models are available"):
                mock_router.route_task("chat", 5, QualityTier.STANDARD)


def test_router_elo_cache_is_lazy(mock_router):
    """ELO cache is empty on construction and only populated after _refresh_elo_cache()."""
    assert mock_router._elo_cache == {}
    assert mock_router._elo_cache_ts == 0.0


def test_router_elo_sort_neutral_when_no_data(mock_router):
    """_apply_elo_sort returns candidates unchanged when ELO cache is empty."""
    from src.core.model_registry import ModelDefinition, Provider

    def make_model(cost: float) -> ModelDefinition:
        return ModelDefinition(
            id=f"provider/model-{cost}",
            name=f"model-{cost}",
            provider=Provider.OPENAI,
            input_cost_per_mtok=cost,
            output_cost_per_mtok=cost,
            max_context_tokens=128000,
            quality_tiers=["standard"],
        )

    cheap = make_model(0.1)
    expensive = make_model(10.0)
    candidates = [cheap, expensive]

    # With no ELO data, sort falls through and returns the input list unchanged
    result = mock_router._apply_elo_sort(candidates)
    assert result == candidates


def test_router_elo_sort_with_data(mock_router):
    """Higher ELO models should appear first in sorted output."""
    from src.core.model_registry import ModelDefinition, Provider

    def make_model(mid: str, cost: float) -> ModelDefinition:
        return ModelDefinition(
            id=mid,
            name=mid,
            provider=Provider.OPENAI,
            input_cost_per_mtok=cost,
            output_cost_per_mtok=cost,
            max_context_tokens=128000,
            quality_tiers=["standard"],
        )

    champion = make_model("openai/gpt-4o", 5.0)
    challenger = make_model("openai/gpt-4o-mini", 0.15)

    # Seed ELO cache: champion has very high ELO, challenger is low
    mock_router._elo_cache = {"openai/gpt-4o": 1500.0, "openai/gpt-4o-mini": 1050.0}
    mock_router._elo_cache_ts = 9e18  # prevent refresh

    result = mock_router._apply_elo_sort([challenger, champion])
    assert result[0].id == "openai/gpt-4o", "Champion should be first despite higher cost"


def test_router_record_and_save_outcome(mock_router, tmp_path):
    """record_outcome appends an entry and _save_history persists it."""
    mock_router.history_file = tmp_path / ".gptcgt" / "routing_history.json"

    mock_router.record_outcome(
        task_id="test-task-001",
        model_id="openai/gpt-4o",
        intent="edit",
        complexity=7,
        success=True,
    )

    assert len(mock_router.outcomes) == 1
    assert mock_router.outcomes[0].success is True
    assert mock_router.history_file.exists()


# ---------------------------------------------------------------------------
# ChatPipeline integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_error_callback_on_no_models(mock_store):
    """Pipeline calls error_callback (not raises) when router finds no models."""
    pipeline = ChatPipeline(mock_store, default_tier=QualityTier.STANDARD)
    errors = []

    async def capture_error(msg: str):
        errors.append(msg)

    with patch("src.core.router.CodingRouter.route_task", side_effect=ValueError("No models")):
        await pipeline.process_message("Hi", error_callback=capture_error)

    assert len(errors) == 1
    assert "No models" in errors[0]


@pytest.mark.asyncio
async def test_pipeline_error_callback_on_missing_key(mock_store):
    """Pipeline error_callback fires when selected model has no API key."""
    pipeline = ChatPipeline(mock_store, default_tier=QualityTier.STANDARD)
    errors = []

    async def capture_error(msg: str):
        errors.append(msg)

    # The fake model override path triggers: registry returns None, no key configured
    await pipeline.process_message(
        "Hello",
        model_id_override="fake/model",
        error_callback=capture_error,
    )

    # Should have received some error (model resolution or missing key)
    assert len(errors) >= 1


# ---------------------------------------------------------------------------
# ContextTruncated event contract test
# ---------------------------------------------------------------------------


def test_context_truncated_event_fields():
    """ContextTruncated event carries reason, tokens_dropped, and files_truncated."""
    event = ContextTruncated(
        reason="History too long",
        tokens_dropped=500,
        files_truncated=["src/foo.py"],
    )
    assert event.reason == "History too long"
    assert event.tokens_dropped == 500
    assert "src/foo.py" in event.files_truncated


def test_reflection_retry_hint_event_fields():
    """ReflectionRetryHint carries model_name, lesson, and trigger_event."""
    event = ReflectionRetryHint(
        model_name="gpt-4o",
        lesson="• Never assume the function exists without checking imports.",
        trigger_event="user_override",
    )
    assert event.model_name == "gpt-4o"
    assert "Never assume" in event.lesson
    assert event.trigger_event == "user_override"
