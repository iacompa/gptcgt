"""Tests for AgentMemory checklist-item linking and context boosting."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.memory import AgentMemory


@pytest.fixture
def agent_mem(tmp_path: Path) -> AgentMemory:
    """Fresh agent memory in a temp directory."""
    return AgentMemory(tmp_path)


class TestChecklistItemLinking:
    """Verify checklist_item_id flows through record → get_context."""

    def test_record_with_item_id(self, agent_mem: AgentMemory) -> None:
        agent_mem.record_interaction(
            agent_id="gpt-4o",
            task_summary="Implement login",
            outcome="failure",
            lesson="Must validate JWT expiry",
            checklist_item_id="abc123def456",
        )
        md = agent_mem._agent_file("gpt-4o").read_text()
        assert "**Item:** `abc123def456`" in md
        assert "**Lesson:** Must validate JWT expiry" in md

    def test_record_without_item_id(self, agent_mem: AgentMemory) -> None:
        agent_mem.record_interaction(
            agent_id="gpt-4o",
            task_summary="Fix typo",
            outcome="success",
        )
        md = agent_mem._agent_file("gpt-4o").read_text()
        assert "**Item:**" not in md

    def test_context_boosts_linked_entries(self, agent_mem: AgentMemory) -> None:
        # Record two lessons — one linked, one not
        agent_mem.record_interaction(
            agent_id="claude-3.5",
            task_summary="Auth flow",
            outcome="failure",
            lesson="Unlinked lesson about error handling",
        )
        agent_mem.record_interaction(
            agent_id="claude-3.5",
            task_summary="Auth flow",
            outcome="failure",
            lesson="Linked lesson about JWT validation",
            checklist_item_id="target_item1",
        )

        # With checklist_item_id, linked entry should appear first
        ctx = agent_mem.get_context("claude-3.5", checklist_item_id="target_item1")
        jwt_pos = ctx.find("JWT validation")
        err_pos = ctx.find("error handling")
        assert jwt_pos < err_pos, "Linked lesson should be boosted to appear first"

    def test_context_without_item_id_unchanged(self, agent_mem: AgentMemory) -> None:
        agent_mem.record_interaction(
            agent_id="gemini-pro",
            task_summary="Build API",
            outcome="failure",
            lesson="Always set content-type headers",
        )
        ctx1 = agent_mem.get_context("gemini-pro")
        ctx2 = agent_mem.get_context("gemini-pro", checklist_item_id="")
        assert ctx1 == ctx2

    def test_backward_compatible_signature(self, agent_mem: AgentMemory) -> None:
        """Old callsites without checklist_item_id still work."""
        agent_mem.record_interaction(
            agent_id="gpt-4o",
            task_summary="Old call",
            outcome="success",
            lesson="Legacy format works",
            files_touched=["src/main.py"],
            cost_usd=0.01,
        )
        ctx = agent_mem.get_context("gpt-4o", max_tokens=500)
        assert "Legacy format works" in ctx
