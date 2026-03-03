"""Tests for DAGTraceEvent emission and DAGEngine execution flow."""


import pytest

from src.core.dag import DAGEngine, DAGNode, TaskState
from src.core.events import DAGTraceEvent
from src.core.model_registry import QualityTier


class SuccessNode(DAGNode):
    name = "success_node"

    async def execute(self, state, context):
        return "next_node"


class TerminalNode(DAGNode):
    name = "next_node"

    async def execute(self, state, context):
        return None  # End execution


class ErrorNode(DAGNode):
    name = "error_node"

    async def execute(self, state, context):
        raise RuntimeError("test error in node")


async def _noop(*a, **kw):
    pass


def _make_state(**overrides):
    """Create a minimal TaskState for testing."""
    defaults = dict(
        user_input="test",
        attached_files=[],
        global_tier=QualityTier.STANDARD,
        narration_callback=_noop,
        yield_chunk_callback=_noop,
        tool_call_callback=_noop,
        thought_callback=_noop,
        error_callback=_noop,
    )
    defaults.update(overrides)
    return TaskState(**defaults)


class TestDAGTraceEvent:
    """Tests for DAGTraceEvent message structure."""

    def test_trace_event_fields(self):
        evt = DAGTraceEvent(node="init", status="running", elapsed_ms=0)
        assert evt.node == "init"
        assert evt.status == "running"
        assert evt.elapsed_ms == 0
        assert evt.next_node is None
        assert evt.error is None

    def test_trace_event_done(self):
        evt = DAGTraceEvent(
            node="gather_context", status="done",
            elapsed_ms=150, next_node="route_task"
        )
        assert evt.status == "done"
        assert evt.elapsed_ms == 150
        assert evt.next_node == "route_task"

    def test_trace_event_error(self):
        evt = DAGTraceEvent(
            node="standard_execution", status="error",
            elapsed_ms=2000, error="timeout"
        )
        assert evt.status == "error"
        assert evt.error == "timeout"


class TestDAGEngineExecution:
    """Tests for DAGEngine.run node traversal."""

    @pytest.mark.asyncio
    async def test_two_node_chain(self):
        engine = DAGEngine(SuccessNode())
        engine.register_node(TerminalNode())
        state = _make_state()
        await engine.run(state, context=None)
        # Should not raise and should complete

    @pytest.mark.asyncio
    async def test_error_node_triggers_error_callback(self):
        errors = []

        async def capture_error(msg):
            errors.append(msg)

        engine = DAGEngine(ErrorNode())
        state = _make_state(error_callback=capture_error)
        await engine.run(state, context=None)
        assert len(errors) == 1
        assert "test error in node" in errors[0]

    @pytest.mark.asyncio
    async def test_halt_execution_stops_engine(self):
        state = _make_state()
        state.halt_execution = True
        engine = DAGEngine(SuccessNode())
        engine.register_node(TerminalNode())
        await engine.run(state, context=None)
        # Should exit immediately without executing any nodes
