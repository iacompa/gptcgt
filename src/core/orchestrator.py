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
from src.core.project_context import ProjectContextGenerator
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
            # 1. Start Mode Management & Cost Tracking
            self.mode_manager.initialize_task(global_tier)
            await narration_callback("Analyzing task intent and scope...", "info")

            # 2. Intent & Relevance Analysis (using Scout/Cheap Model)
            analysis = await self._analyze_intent_and_scope(user_input, attached_files, global_tier)
            await narration_callback(
                f"Determined intent: {analysis['intent']} (Complexity: {analysis['complexity']}/10)",  # noqa: E501
                "decision",
            )

            # 3. Gather Context
            relevant_files = []
            if analysis["intent"] in ["question", "edit", "create", "debug"]:
                await narration_callback("Searching codebase for relevant context...", "info")
                relevant_files = self.repo_map.find_relevant_files(
                    mentioned_files=analysis.get("mentioned_files", []),
                    mentioned_symbols=analysis.get("mentioned_symbols", []),
                )
                if relevant_files:
                    await narration_callback(
                        f"Found {len(relevant_files)} relevant files.", "result"
                    )
                    try:
                        import textual.app as _tapp
                        from src.core.events import FileRelevanceUpdated

                        _tapp.active_app.get().post_message(
                            FileRelevanceUpdated(files=relevant_files)
                        )
                    except Exception as e:
                        logger.debug(f"Could not post FileRelevanceUpdated to UI: {e}")

            # 4. Route to Model
            provider_family = None
            if self.mode_manager.active_mode.name.startswith("SINGLE_MODEL_"):
                provider_family = self.mode_manager.active_mode.value.replace("single_model_", "")

            selected_model = self.router.route_task(
                analysis["intent"], analysis["complexity"], global_tier, provider_family, role="orchestrator"
            )
            if model_selected_callback:
                await model_selected_callback(selected_model.name)
            await narration_callback(
                f"Routed to {selected_model.name} based on complexity and tier.", "routing"
            )

            # 5. Build Project Context if needed
            from src.core.workspace import Workspace

            ws = Workspace.get_instance()
            gptcgt_dir = ws.get_project_root() / ".gptcgt"
            if not (gptcgt_dir / "project.md").exists():
                pcg = ProjectContextGenerator()
                pcg.generate_and_save()

            # 6. Execute via Pipeline
            is_standard = self.mode_manager.active_mode in (
                OperationMode.STANDARD,
                OperationMode.SCOUT,
            ) or self.mode_manager.active_mode.name.startswith("SINGLE_MODEL_")
            if is_standard:
                await narration_callback(
                    f"Executing task in {self.mode_manager.active_mode.name} mode...", "info"
                )

                from src.core.events import AgentStatusUpdate
                try:
                    import textual.app as _tapp
                    _tui_app = _tapp.active_app.get()
                    _tui_app.post_message(AgentStatusUpdate(
                        agent_id="orch",
                        model_name=selected_model.name,
                        status="thinking",
                        detail="Cross-referencing memory...",
                    ))
                except Exception:
                    pass

                from src.core.chat_pipeline import ChatPipeline

                pipeline = ChatPipeline(self.chat_store, global_tier)

                # Inject any pending reflection lesson as a system-level context hint.
                # The ReflectionEngine writes a lesson after user aborts; ChatPanel
                # stores it in _pending_reflection_hint. We inject it once here and
                # clear it so it's not repeated. This closes the ARCH-REFLECT loop.
                reflection_hint: str | None = None
                try:
                    import textual.app as _tapp
                    from src.tui.panels.chat import ChatPanel
                    _chat = _tapp.active_app.get().query_one(ChatPanel)
                    if _chat._pending_reflection_hint:
                        reflection_hint = _chat._pending_reflection_hint
                        _chat._pending_reflection_hint = None  # consume it
                except Exception:
                    pass

                response_text = ""

                async def intercept_yield(chunk: str):
                    nonlocal response_text
                    response_text += chunk
                    await yield_chunk_callback(chunk)

                # P0 Fix: Inject scout-discovered relevant files into pipeline context
                merged_files = list(attached_files) if attached_files else []
                if relevant_files:
                    ws = Workspace.get_instance()
                    for rf in relevant_files[:10]:  # Cap at 10 to protect token budget
                        rf_path = str(rf)
                        if not any(af.get("path") == rf_path for af in merged_files):
                            try:
                                content = ws.safe_read(rf_path)
                                if content:
                                    merged_files.append({"path": rf_path, "content": content[:4000]})
                            except Exception:
                                pass

                await pipeline.process_message(
                    user_text=user_input,
                    attached_files=merged_files if merged_files else None,
                    model_id_override=selected_model.id,
                    yield_chunk_callback=intercept_yield,
                    tool_call_callback=tool_call_callback,
                    thought_callback=thought_callback,
                    error_callback=error_callback,
                    cancel_event=cancel_event,
                    complexity=analysis.get("complexity", 5),
                    reflection_hint=reflection_hint,
                )
                self._extract_annotations_from_response(response_text)
            else:
                await narration_callback(
                    f"Executing task in {self.mode_manager.active_mode.name} mode...", "info"
                )


                from src.core.arbiter import Arbiter
                from src.core.events import (
                    ArbiterVerdictReady,
                    MultiAgentChunk,
                    MultiAgentToolCall,
                    ParallelAgentComplete,
                    ParallelDispatchComplete,
                    ParallelDispatchStarted,
                    PatchSetProposed,
                )
                from src.core.parallel_dispatcher import ParallelDispatcher
                from src.core.security import SecurityScanner
                from src.core.workspace import Workspace
                from src.tools.lsp import LSPClient
                from src.tools.sandbox import E2BSandbox

                import textual.app as _tapp
                _tui_app = _tapp.active_app.get()
                sandbox = E2BSandbox()
                ws = Workspace.get_instance()
                security = SecurityScanner(ws.get_project_root())
                lsp = LSPClient(ws.get_project_root())
                arbiter = Arbiter(sandbox, security, lsp)
                dispatcher = ParallelDispatcher()

                count = 2 if self.mode_manager.active_mode == OperationMode.BATTLE else 3
                models = self.router.get_parallel_models(count)

                from src.core.system_prompt import SystemPromptBuilder

                sys_prompt = SystemPromptBuilder.build(model_name="orchestrator")
                context_messages = [{"role": "system", "content": sys_prompt}]
                for f in attached_files:
                    context_messages.append(
                        {"role": "user", "content": f"File {f['path']}:\n{f['content']}"}
                    )
                context_messages.append({"role": "user", "content": user_input})

                from src.tools.tool_registry import get_tool_definitions

                tools = get_tool_definitions()

                if self.mode_manager.active_mode == OperationMode.ARCHITECT:
                    from src.core.architect import ArchitectPipeline

                    arch_pipeline = ArchitectPipeline(dispatcher, arbiter)
                    event_stream = arch_pipeline.run_planning_phase(
                        user_input, context_messages, models, tools
                    )
                else:
                    mode_str = (
                        "battle"
                        if self.mode_manager.active_mode == OperationMode.BATTLE
                        else "ensemble"
                    )
                    event_stream = dispatcher.dispatch(
                        user_input, context_messages, models, tools, mode=mode_str
                    )

                current_dispatch_id = ""
                agent_texts = {}
                async for event in event_stream:
                    if cancel_event and cancel_event.is_set():
                        import asyncio

                        raise asyncio.CancelledError("Task generation cancelled by user")

                    if event["type"] == "dispatch_started":
                        current_dispatch_id = event["dispatch_id"]
                        _tui_app.post_message(
                            ParallelDispatchStarted(
                                current_dispatch_id,
                                self.mode_manager.active_mode.name,
                                event["agents"],
                            )
                        )
                    elif event["type"] == "agent_chunk":
                        agent_id = event["agent_id"]
                        agent_texts[agent_id] = agent_texts.get(agent_id, "") + event["text"]
                        _tui_app.post_message(
                            MultiAgentChunk(
                                dispatch_id=current_dispatch_id,
                                agent_id=agent_id,
                                text=event["text"],
                            )
                        )
                    elif event["type"] == "agent_tool_call":
                        _tui_app.post_message(
                            MultiAgentToolCall(
                                dispatch_id=current_dispatch_id,
                                agent_id=event["agent_id"],
                                tool_name=event["tool_name"],
                                args=event["args"],
                            )
                        )
                    elif event["type"] == "agent_complete":
                        _tui_app.post_message(
                            ParallelAgentComplete(
                                dispatch_id=current_dispatch_id,
                                agent_id=event["agent_id"],
                                result={
                                    "duration_ms": event.get("duration_ms", 0),
                                    "cost_usd": event.get("cost_usd", 0.0),
                                },
                            )
                        )
                    elif event["type"] == "error":
                        if error_callback:
                            await error_callback(event.get("error", "Unknown error"))
                    elif event["type"] == "all_complete":
                        dispatch = event["dispatch"]
                        _tui_app.post_message(ParallelDispatchComplete(dispatch))
                        if self.mode_manager.active_mode != OperationMode.ARCHITECT:
                            await narration_callback(
                                "Running 6-stage Arbiter evaluation on patches...", "info"
                            )

                            async def on_progress(stage, agent_id, detail):
                                await narration_callback(f"Arbiter [{stage}]: {detail}", "decision")

                            verdict = await arbiter.evaluate(
                                dispatch, ws.get_project_root(), "python", on_progress=on_progress
                            )
                            _tui_app.post_message(ArbiterVerdictReady(verdict))

                            from src.core.diff_engine import MultiAgentPatchSet

                            valid_patches = [
                                s.patch_set
                                for s in verdict.scores
                                if s.patch_set and not s.eliminated
                            ]
                            if valid_patches:
                                multi_ps = MultiAgentPatchSet(patch_sets=valid_patches)
                                _tui_app.post_message(PatchSetProposed(patch_set=multi_ps))

                    elif event["type"] == "arbiter_verdict":
                        _tui_app.post_message(ArbiterVerdictReady(event["verdict"]))

                for text in agent_texts.values():
                    self._extract_annotations_from_response(text)

                await lsp.shutdown_all()

            await narration_callback("Task completed.", "result")

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

    async def _analyze_intent_and_scope(
        self, text: str, files: list[dict], tier: QualityTier
    ) -> dict[str, Any]:
        """Uses a lightning-fast QualityTier.LIGHT LLM model to mathematically analyze complexity."""
        from src.core.events import AgentStatusUpdate
        from src.core.intent_analyzer import IntentAnalyzer

        try:
            import textual.app as _tapp
            current_app = _tapp.active_app.get()
            current_app.post_message(AgentStatusUpdate(
                agent_id="orch",
                model_name="Orchestrator",
                status="thinking",
                detail="Analyzing complexity...",
            ))
        except Exception:
            pass

        analyzer = IntentAnalyzer()
        results = await analyzer.analyze(text, files)

        if results.get("intent") == "architect":
            self.mode_manager.set_mode(OperationMode.ARCHITECT)

        try:
            import textual.app as _tapp
            current_app = _tapp.active_app.get()
            current_app.post_message(AgentStatusUpdate(
                agent_id="orch",
                model_name="Orchestrator",
                status="completed",
                detail="",
            ))
        except Exception:
            pass

        return results
