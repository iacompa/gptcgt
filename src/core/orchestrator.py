# ruff: noqa: E501

"""
The central Orchestrator engine.
Categorizes intent (Chat vs Question vs Edit vs Create).
Gathers relevant files using RepoMap. Evaluates complexity.
Dispatches to the Router to select the final model.
"""

from __future__ import annotations

from typing import Any

from src.core.chat_store import ChatStore
from src.core.logger import get_logger
from src.core.mode_manager import ModeManager, OperationMode
from src.core.model_registry import QualityTier
from src.core.router import CodingRouter
from src.tools.repo_map import RepoMap

logger = get_logger("core.orchestrator")


class Orchestrator:
    def __init__(self, chat_store: ChatStore):
        self.chat_store = chat_store
        self.router = CodingRouter()
        self.mode_manager = ModeManager()
        self.repo_map = RepoMap()

    async def process_task(
        self,
        user_input: str,
        attached_files: list[dict],
        global_tier: QualityTier,
        narration_callback,
        yield_chunk_callback,
        tool_call_callback,
        thought_callback,
        error_callback,
        model_selected_callback=None,
        cancel_event=None,
    ) -> None:
        try:
            from src.core.dag import DAGEngine, TaskState
            from src.core.dag_nodes import (
                ArchitectExecuteNode,
                ArchitectPlanNode,
                FinalizeNode,
                GatherContextNode,
                InitAnalyzeNode,
                ParallelExecutionNode,
                PrepareBlackboardNode,
                RouteTaskNode,
                StandardExecutionNode,
            )

            state = TaskState(
                user_input=user_input,
                attached_files=attached_files,
                global_tier=global_tier,
                narration_callback=narration_callback,
                yield_chunk_callback=yield_chunk_callback,
                tool_call_callback=tool_call_callback,
                thought_callback=thought_callback,
                error_callback=error_callback,
                model_selected_callback=model_selected_callback,
                cancel_event=cancel_event,
            )

            engine = DAGEngine(InitAnalyzeNode())
            engine.register_node(GatherContextNode())
            engine.register_node(RouteTaskNode())
            engine.register_node(PrepareBlackboardNode())
            engine.register_node(ArchitectPlanNode())
            engine.register_node(ArchitectExecuteNode())
            engine.register_node(StandardExecutionNode())
            engine.register_node(ParallelExecutionNode())
            engine.register_node(FinalizeNode())

            await engine.run(state, context=self)

        except Exception as e:
            logger.error(f"Orchestrator failed: {e}")
            await narration_callback(f"Orchestrator error: {str(e)}", "error")
            if error_callback:
                await error_callback(str(e))

    def _extract_annotations_from_response(self, text: str) -> None:
        """
        Perform best-effort parsing of inline annotations from the agent response
        and emit AnnotationsReady events.
        Expected format (example):
        <annotation file="src/main.py" line="42" severity="warning" actions="Refactor,Ignore">Missing docstring</annotation>  # noqa: E501
        """
        import re

        pattern = r'<annotation\s+file="([^"]+)"\s+line="(\d+)"\s+severity="([^"]+)"(?:\s+actions="([^"]+)")?>([^<]+)</annotation>'  # noqa: E501
        matches = re.finditer(pattern, text)

        file_annotations = {}
        for m in matches:
            file_path = m.group(1)
            line = int(m.group(2))
            sev = m.group(3)
            actions_str = m.group(4) if m.group(4) else ""
            msg = m.group(5).strip()

            actions = [a.strip() for a in actions_str.split(",") if a.strip()]

            if file_path not in file_annotations:
                file_annotations[file_path] = []

            file_annotations[file_path].append(
                {"line_number": line, "severity": sev, "message": msg, "actions": actions}
            )

        try:
            import textual.app as _tapp

            from src.core.events import AnnotationsReady

            current_app = _tapp.active_app.get()
            for fp, anns in file_annotations.items():
                current_app.post_message(AnnotationsReady(file_path=fp, annotations=anns))
            if file_annotations:
                logger.info(
                    f"Extracted {sum(len(a) for a in file_annotations.values())} annotations from response"  # noqa: E501
                )
        except Exception as e:
            logger.error(f"Failed to post AnnotationsReady event: {e}")

    async def _analyze_intent_and_scope(self, text: str, files: list[dict], tier: QualityTier) -> dict[str, Any]:
        """Uses a lightning-fast QualityTier.LIGHT LLM model to mathematically analyze complexity."""
        from src.core.events import AgentStatusUpdate
        from src.core.intent_analyzer import IntentAnalyzer

        try:
            import textual.app as _tapp

            current_app = _tapp.active_app.get()
            current_app.post_message(
                AgentStatusUpdate(
                    agent_id="orch",
                    model_name="Orchestrator",
                    status="thinking",
                    detail="Analyzing complexity...",
                )
            )
        except Exception:
            pass

        analyzer = IntentAnalyzer()
        results = await analyzer.analyze(text, files)

        if results.get("intent") == "architect":
            self.mode_manager.set_mode(OperationMode.ARCHITECT)

        try:
            import textual.app as _tapp

            current_app = _tapp.active_app.get()
            current_app.post_message(
                AgentStatusUpdate(
                    agent_id="orch",
                    model_name="Orchestrator",
                    status="completed",
                    detail="",
                )
            )
        except Exception:
            pass

        return results
