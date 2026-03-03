"""
Directed Acyclic Graph (DAG) state machine for Orchestrator execution.
Breaks down the monolithic process_task into robust, testable nodes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable

from src.core.logger import get_logger
from src.core.model_registry import ModelDefinition, QualityTier

logger = get_logger("core.dag")


@dataclass
class TaskState:
    """Encapsulates the mutable state as it flows through the DAG pipeline."""

    user_input: str
    attached_files: list[dict]
    global_tier: QualityTier

    # Callbacks
    narration_callback: Callable
    yield_chunk_callback: Callable
    tool_call_callback: Callable
    thought_callback: Callable
    error_callback: Callable
    model_selected_callback: Callable | None = None  # (role: str, model_name: str)
    cancel_event: asyncio.Event | None = None

    # State populated during execution
    intent: str = "chat"
    complexity: int = 5
    analysis_results: dict[str, Any] = field(default_factory=dict)
    relevant_files: list[Any] = field(default_factory=list)
    selected_model: ModelDefinition | None = None
    is_architect_task: bool = False

    # Working data
    agent_texts: dict[str, str] = field(default_factory=dict)
    final_response: str = ""
    is_confused: bool = False

    # Control flow flags
    halt_execution: bool = False


class DAGNode:
    """Base class for all discrete steps in the Orchestrator DAG."""

    name: str = "BaseNode"

    async def execute(self, state: TaskState, context: Any) -> str | None:
        """
        Executes the logic for this node.
        # noqa: W293
        Args:
            state: The mutable TaskState object.
            context: A reference to the parent Orchestrator for accessing shared resources (mode_manager, etc).
        # noqa: W293
        Returns:
            The name of the next node to transition to, or None to finish execution.

        """
        raise NotImplementedError

    async def _check_cancel(self, state: TaskState):
        if state.cancel_event and state.cancel_event.is_set():
            raise asyncio.CancelledError("Task generation cancelled by user")


class DAGEngine:
    """Runs the execution graph sequentially."""

    def __init__(self, initial_node: DAGNode):
        self._nodes: dict[str, DAGNode] = {}
        self.register_node(initial_node)
        self._initial_node_name = initial_node.name

    def register_node(self, node: DAGNode) -> None:
        self._nodes[node.name] = node

    async def run(self, state: TaskState, context: Any) -> None:
        current_node_name = self._initial_node_name

        while current_node_name and not state.halt_execution:
            node = self._nodes.get(current_node_name)
            if not node:
                raise ValueError(f"DAG Node '{current_node_name}' not found.")

            logger.debug(f"[DAG] Entering node: {current_node_name}")
            self._post_trace(current_node_name, "running")
            import time
            t0 = time.monotonic()

            try:
                next_node_name = await node.execute(state, context)
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                self._post_trace(
                    current_node_name, "done",
                    elapsed_ms=elapsed_ms, next_node=next_node_name,
                )
                current_node_name = next_node_name
            except asyncio.CancelledError:
                logger.info(f"[DAG] Execution cancelled at {current_node_name}")
                raise
            except Exception as e:
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                self._post_trace(
                    current_node_name, "error",
                    elapsed_ms=elapsed_ms, error=str(e),
                )
                logger.error(f"[DAG] Error in {current_node_name}: {e}", exc_info=True)
                if state.error_callback:
                    await state.error_callback(str(e))
                break

    @staticmethod
    def _post_trace(
        node: str, status: str, elapsed_ms: int = 0,
        next_node: str | None = None, error: str | None = None,
    ) -> None:
        """Safely post a DAGTraceEvent to the active Textual app."""
        try:
            import textual.app as _tapp

            from src.core.events import DAGTraceEvent
            app = _tapp.active_app.get()
            app.post_message(DAGTraceEvent(
                node=node, status=status,
                elapsed_ms=elapsed_ms, next_node=next_node, error=error,
            ))
        except Exception:
            pass
