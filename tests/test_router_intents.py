from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.model_registry import QualityTier
from src.core.orchestrator import Orchestrator
from src.core.router import CodingRouter, TaskIntent


@pytest.mark.asyncio
async def test_orchestrator_heuristic_intent_assignments():
    orch = Orchestrator(MagicMock())
    orch.mode_manager = AsyncMock()

    async def get_intent(text):
        res = await orch._analyze_intent_and_scope(text, [], QualityTier.STANDARD)
        return res["intent"]

    # Debug
    assert await get_intent("Please fix this bug") == TaskIntent.DEBUG.value
    assert await get_intent("Debug the proxy error") == TaskIntent.DEBUG.value

    # Create
    assert await get_intent("Write a new function to do X") == TaskIntent.CREATE.value
    assert await get_intent("Implement missing core feature") == TaskIntent.CREATE.value

    # Edit
    assert await get_intent("Refactor the login module") == TaskIntent.EDIT.value
    assert await get_intent("Modify the permissions") == TaskIntent.EDIT.value

    # Architect
    assert await get_intent("Build an app from scratch") == TaskIntent.ARCHITECT.value

    # Question
    assert await get_intent("Explain what this does") == TaskIntent.QUESTION.value
    assert await get_intent("How does it work") == TaskIntent.QUESTION.value

    # Chat fallback
    assert await get_intent("Hello") == TaskIntent.CHAT.value


def test_router_handles_all_intents():
    router = CodingRouter()

    # Mocking registry so it doesn't try to load unconfigured models
    class MockRegistry:
        def get_available_models(self):
            class MockModel:
                def __init__(self, t, cost):
                    self.quality_tiers = [t.value]
                    self.input_cost_per_mtok = cost
                    self.provider = MagicMock(value="mock")

            # Premium
            m1 = MockModel(QualityTier.MAX, 10.0)

            # Standard/Light
            m2 = MockModel(QualityTier.STANDARD, 1.0)
            m2.quality_tiers.append(QualityTier.LIGHT.value)
            return [m1, m2]

    router.registry = MockRegistry()

    # Chat intent with low complexity should use light/standard
    model = router.route_task(
        intent=TaskIntent.CHAT.value, complexity=2, global_tier=QualityTier.MAX
    )
    assert QualityTier.LIGHT.value in model.quality_tiers or QualityTier.STANDARD.value in model.quality_tiers

    # Create intent with high complexity should use Premium
    model = router.route_task(
        intent=TaskIntent.CREATE.value, complexity=9, global_tier=QualityTier.MAX
    )
    assert QualityTier.MAX.value in model.quality_tiers

    # Debug intent with high complexity should use Premium
    model = router.route_task(
        intent=TaskIntent.DEBUG.value, complexity=8, global_tier=QualityTier.MAX
    )
    assert QualityTier.MAX.value in model.quality_tiers
