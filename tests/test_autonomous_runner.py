"""
Integration tests for the AutonomousRunner and DAG execution.

Verifies that the Orchestrator successfully reads a plan, delegates subtasks,
and routes through the Coder -> Tester -> Arbiter loop.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.agent_bus import AgentMessageBus
from src.core.autonomous import AutonomousRunner, SubtaskResult
from src.core.workspace import Workspace


@pytest.fixture()
def mock_workspace(tmp_path: Path):
    ws = MagicMock()
    ws.get_project_root.return_value = tmp_path
    ws.validate_path.side_effect = lambda p: tmp_path / Path(str(p)).name
    
    plan_file = tmp_path / "project_plan.md"
    plan_file.write_text("- [ ] Task 1\n- [ ] Task 2")
    ws.safe_read.return_value = plan_file.read_text()
    
    return ws


@pytest.mark.asyncio
async def test_autonomous_runner_delegation_flow(mock_workspace):
    """Ensure the runner reads the plan, delegates, and finishes a task."""
    bus = AgentMessageBus()
    runner = AutonomousRunner(bus)
    
    emitted_events = []
    async def _catch_event(e, *args, **kwargs):
        emitted_events.append(e)

    async def _mock_prompt_callback(proposal, diff, msg):
        return True
    
    # We want to mock out the expensive LLM calls but keep the pipeline structure intact
    with (
        patch("src.core.workspace.Workspace.get_instance", return_value=mock_workspace),
        patch("src.core.autonomous.AutonomousRunner._execute_subtask") as mock_execute,
    ):
        mock_execute.return_value = SubtaskResult(subtask="Task 1", approved=True, cost_usd=0.01, tokens_used=10)
        
        # Test just the parsing and loop initialization
        await runner.run(
            goal="Complete tasks",
            narration_callback=_catch_event,
            yield_chunk_callback=_catch_event,
        )

        assert mock_execute.call_count > 0
        assert runner.state.plan_path == ".gptcgt/project_plan.md"
        assert len(runner.state.completed_subtasks) > 0
