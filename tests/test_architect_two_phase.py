"""Tests for 2-phase architect mode in the orchestrator."""

import inspect

import pytest

from src.core.blackboard import AgentBlackboard
from src.core.task_brief import TaskBrief


class TestTaskBriefValidation:
    def test_valid_brief(self):
        brief = TaskBrief(intent="edit", user_request="fix the bug", complexity=5)
        brief.validate()  # Should not raise

    def test_missing_intent_raises(self):
        brief = TaskBrief(intent="", user_request="fix the bug", complexity=5)
        with pytest.raises(ValueError, match="intent is required"):
            brief.validate()

    def test_missing_user_request_raises(self):
        brief = TaskBrief(intent="edit", user_request="", complexity=5)
        with pytest.raises(ValueError, match="user_request is required"):
            brief.validate()

    def test_invalid_complexity_raises(self):
        brief = TaskBrief(intent="edit", user_request="fix", complexity=0)
        with pytest.raises(ValueError, match="complexity must be 1-10"):
            brief.validate()

    def test_complexity_over_10_raises(self):
        brief = TaskBrief(intent="edit", user_request="fix", complexity=11)
        with pytest.raises(ValueError, match="complexity must be 1-10"):
            brief.validate()

    def test_to_system_context_validates(self):
        """to_system_context calls validate() internally."""
        brief = TaskBrief(intent="", user_request="fix", complexity=5)
        with pytest.raises(ValueError):
            brief.to_system_context()


class TestBlackboardArchitectPhase:
    @pytest.fixture(autouse=True)
    def reset_bb(self):
        bb = AgentBlackboard.get_instance()
        bb.clear()
        yield
        bb.clear()

    def test_architect_plan_written_to_blackboard(self):
        bb = AgentBlackboard.get_instance()
        bb.write("architect_plan", "1. Create module\n2. Add tests", author="architect")
        assert "architect_plan" in bb._entries
        assert bb.read("architect_plan") == "1. Create module\n2. Add tests"

    def test_blackboard_context_includes_plan(self):
        bb = AgentBlackboard.get_instance()
        bb.write("architect_plan", "Step 1: Design API", author="architect")
        context = bb.to_context_string()
        assert "architect_plan" in context
        assert "Step 1: Design API" in context


class TestOrchestratorArchitectDetection:
    def test_orchestrator_has_architect_mode(self):
        """Orchestrator source must contain architect 2-phase logic."""
        from src.core import orchestrator
        source = inspect.getsource(orchestrator)
        assert "is_architect_task" in source, "Orchestrator missing 2-phase architect detection"
        assert "Phase 1" in source, "Orchestrator missing Phase 1 plan generation"
        assert "Phase 2" in source, "Orchestrator missing Phase 2 constrained execution"
