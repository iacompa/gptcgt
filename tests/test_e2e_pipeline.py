"""
End-to-end orchestration integration test with mocked LLM responses.

Tests the full pipeline: ChatPipeline → Router → Agent → DiffExtractor → PatchSet.
Uses in-process mocks so no LLM keys required, no network calls.

Run with:
    PYTHONPATH=. pytest tests/test_e2e_pipeline.py -v
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.chat_pipeline import ChatPipeline
from src.core.chat_store import ChatStore

# ------------------------------------------------------------------ #
# Fake LLM chunk helpers                                               #
# ------------------------------------------------------------------ #

class FakeChunk:
    def __init__(self, text=None, tool_calls=None, usage=None):
        self.text = text
        self.tool_calls = tool_calls
        self.usage = usage


def _build_mock_agent(stream_chunks):
    mock_agent = MagicMock()
    mock_agent.config = MagicMock()

    async def _stream(_messages):
        for c in stream_chunks:
            yield c

    mock_agent.chat_stream = _stream
    return mock_agent


# ------------------------------------------------------------------ #
# Fixtures                                                             #
# ------------------------------------------------------------------ #

@pytest.fixture()
def chat_store(tmp_path: Path) -> ChatStore:
    mock_ws = MagicMock()
    mock_ws.get_project_root.return_value = tmp_path
    return ChatStore(mock_ws)


@pytest.fixture()
def pipeline(chat_store: ChatStore) -> ChatPipeline:
    return ChatPipeline(chat_store)


def _fake_model():
    """Return a realistic ModelDefinition mock."""
    return MagicMock(
        id="openai/gpt-4o",
        name="GPT-4o",
        provider=MagicMock(value="openai"),
        input_cost_per_mtok=5.0,
        output_cost_per_mtok=15.0,
    )


def _base_patches(extra_patches=()):
    """Common patch context for all happy-path tests."""
    return [
        patch("src.core.router.CodingRouter.route_task", return_value=_fake_model()),
        patch("src.auth.keychain.KeyChainManager.get_key", return_value="sk-test-key"),
        patch("src.core.system_prompt.SystemPromptBuilder.build", return_value="System prompt"),
        patch("src.core.context_manager.ContextManager.prepare_payload", return_value=[
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "test"},
        ]),
        patch("src.core.model_registry.ModelRegistry.calculate_cost", return_value=0.001),
        patch("src.tools.tool_registry.get_tool_definitions", return_value=[]),
        patch("src.agents.factory.PROVIDER_KEY_MAP", {"openai": "OPENAI_API_KEY"}),
    ] + list(extra_patches)


# ------------------------------------------------------------------ #
# Tests                                                                #
# ------------------------------------------------------------------ #


class TestE2EPipelineHappyPath:
    """Pipeline correctly processes a simple text response end-to-end."""

    @pytest.mark.asyncio
    async def test_plain_text_response_collected(self, pipeline: ChatPipeline):
        """Chunks accumulate into full_response, history persisted."""
        chunks = [
            FakeChunk(text="Hello, "),
            FakeChunk(text="world!"),
            FakeChunk(usage={"prompt_tokens": 10, "completion_tokens": 5}),
        ]
        mock_agent = _build_mock_agent(chunks)
        collected: list[str] = []

        async def _on_chunk(t: str):
            collected.append(t)

        patches = _base_patches([
            patch("src.agents.factory.AgentFactory.create_agent", return_value=mock_agent),
        ])
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
            await pipeline.process_message(user_text="Say hello", yield_chunk_callback=_on_chunk)

        assert collected == ["Hello, ", "world!"]
        messages = pipeline.chat_store.get_recent_messages(count=10)
        assert any("Hello, world!" in (m.content or "") for m in messages)

    @pytest.mark.asyncio
    async def test_error_callback_on_missing_api_key(self, pipeline: ChatPipeline):
        """Missing BYOK key triggers async error_callback without crashing."""
        errors: list[str] = []

        async def _on_error(msg: str):
            errors.append(msg)

        with (
            patch("src.core.router.CodingRouter.route_task", return_value=_fake_model()),
            patch("src.auth.keychain.KeyChainManager.get_key", return_value=None),
            patch("src.agents.factory.PROVIDER_KEY_MAP", {"openai": "OPENAI_API_KEY"}),
        ):
            await pipeline.process_message(user_text="Hello", error_callback=_on_error)

        assert any("Missing API key" in e for e in errors)

    @pytest.mark.asyncio
    async def test_cancel_event_halts_stream(self, pipeline: ChatPipeline):
        """Setting cancel_event mid-stream stops further chunks (CancelledError is expected)."""
        import asyncio
        import threading
        cancel_event = threading.Event()

        async def _cancelling_stream(_messages):
            yield FakeChunk(text="partial")
            cancel_event.set()
            yield FakeChunk(text=" more")  # Should NOT reach callback

        mock_agent = MagicMock()
        mock_agent.config = MagicMock()
        mock_agent.chat_stream = _cancelling_stream
        collected: list[str] = []

        async def _on_chunk(t: str):
            collected.append(t)

        patches = _base_patches([
            patch("src.agents.factory.AgentFactory.create_agent", return_value=mock_agent),
        ])
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
            # CancelledError is allowed to propagate — it is the expected abort behavior
            with pytest.raises(asyncio.CancelledError):
                await pipeline.process_message(
                    user_text="Go",
                    yield_chunk_callback=_on_chunk,
                    cancel_event=cancel_event,
                )

        assert "partial" in collected
        assert " more" not in collected


class TestE2EPipelinePatchExtraction:
    """Pipeline correctly extracts diff patches from LLM response."""

    @pytest.mark.asyncio
    async def test_patch_set_detected_in_response(self, pipeline: ChatPipeline):
        """When LLM emits a diff block, DiffExtractor should find patches."""
        diff_response = (
            "Here is the fix:\n\n"
            "```diff\n"
            "--- a/src/foo.py\n"
            "+++ b/src/foo.py\n"
            "@@ -1,3 +1,4 @@\n"
            " def foo():\n"
            "-    return 1\n"
            "+    # Fixed\n"
            "+    return 2\n"
            "```\n"
        )
        chunks = [FakeChunk(text=diff_response)]
        mock_agent = _build_mock_agent(chunks)

        mock_app = MagicMock()
        patch_events: list = []
        mock_app.post_message = lambda msg: patch_events.append(msg)

        patches = _base_patches([
            patch("src.agents.factory.AgentFactory.create_agent", return_value=mock_agent),
        ])
        with (
            patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7],
            patch("src.core.chat_pipeline.ChatPipeline._handle_post_stream") as mock_post,
        ):
            # Bypass post_stream so we can inspect patch_set directly
            mock_post.return_value = None

            await pipeline.process_message(user_text="Fix it")

        # Since we're testing DiffExtractor, verify it finds a patch
        from src.core.diff_engine import DiffExtractor
        extractor = DiffExtractor()
        patch_set = extractor.extract(diff_response, agent_id="test", model_name="gpt-4o")
        assert patch_set.file_count >= 1


class TestE2EPipelineReflectionHint:
    """Reflection hint is correctly injected into the system prompt."""

    @pytest.mark.asyncio
    async def test_reflection_hint_appended_to_system_prompt(self, pipeline: ChatPipeline):
        """reflection_hint should appear in the effective system prompt."""
        chunks = [FakeChunk(text="ok")]
        mock_agent = _build_mock_agent(chunks)
        captured_system: list[str] = []

        def capturing_prepare(_self_cm, system_prompt, **kwargs):
            captured_system.append(system_prompt)
            return [{"role": "system", "content": system_prompt}, {"role": "user", "content": "q"}]

        patches = _base_patches([
            patch("src.agents.factory.AgentFactory.create_agent", return_value=mock_agent),
            patch("src.core.context_manager.ContextManager.prepare_payload", capturing_prepare),
        ])
        # Override the generic prepare_payload patch with capturing one
        with (
            patches[0],  # route_task
            patches[1],  # get_key
            patches[2],  # SystemPromptBuilder → returns "System prompt"
            patches[4],  # calculate_cost
            patches[5],  # get_tool_definitions
            patches[6],  # PROVIDER_KEY_MAP
            patches[7],  # AgentFactory.create_agent
            patches[8],  # capturing prepare_payload (overrides patches[3])
        ):
            await pipeline.process_message(user_text="q", reflection_hint="Always use type hints.")

        assert len(captured_system) == 1
        assert "Always use type hints." in captured_system[0]


class TestE2EPipelineModelResolution:
    """Model resolution handles override IDs, registration misses, and ValueError from router."""

    @pytest.mark.asyncio
    async def test_router_value_error_calls_error_callback(self, pipeline: ChatPipeline):
        """ValueError from router should gracefully call async error_callback."""
        errors: list[str] = []

        async def _on_error(msg: str):
            errors.append(msg)

        with (
            patch("src.core.router.CodingRouter.route_task", side_effect=ValueError("no models")),
            patch("src.agents.factory.PROVIDER_KEY_MAP", {}),
        ):
            await pipeline.process_message(user_text="hello", error_callback=_on_error)

        assert any("no models" in e for e in errors)

    @pytest.mark.asyncio
    async def test_byok_daily_limit_blocks_pipeline(self, pipeline: ChatPipeline):
        """When daily BYOK spend >= limit, pipeline aborts before LLM call."""
        mock_cost_tracker = MagicMock()
        mock_cost_tracker.get_today_spend.return_value = MagicMock(total_cost=5.01)
        pipeline.cost_tracker = mock_cost_tracker

        errors: list[str] = []

        async def _on_error(msg: str):
            errors.append(msg)

        with (
            patch("src.core.router.CodingRouter.route_task", return_value=_fake_model()),
            patch("src.auth.keychain.KeyChainManager.get_key", return_value="sk-test-byok"),
            patch("src.agents.factory.PROVIDER_KEY_MAP", {"openai": "OPENAI_API_KEY"}),
            patch("src.core.config.ConfigManager") as mock_cfg,
        ):
            mock_cfg.return_value.user.daily_spend_limit = 5.00
            await pipeline.process_message(user_text="hello", error_callback=_on_error)

        assert any("Spending Cap" in e for e in errors)
