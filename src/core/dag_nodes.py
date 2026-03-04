from __future__ import annotations

from typing import Any

from src.core.dag import DAGNode, TaskState
from src.core.logger import get_logger
from src.core.mode_manager import OperationMode
from src.core.model_registry import QualityTier

logger = get_logger("core.dag_nodes")

class InitAnalyzeNode(DAGNode):
    name = "init_analyze"
    async def execute(self, state: TaskState, ctx: Any) -> str | None:
        await self._check_cancel(state)
        ctx.mode_manager.initialize_task(state.global_tier)

        # Handle 2-Phase Architect Mode Continuation
        if state.user_input.strip() == "SYSTEM_INTERNAL_CMD::EXECUTE_ARCHITECT_PLAN":
            state.intent = "architect_execute"
            state.complexity = 10
            state.analysis_results = {"intent": "architect_execute", "complexity": 10}
            return "gather_context"

        await state.narration_callback("Analyzing task intent and scope...", "info")

        analysis = await ctx._analyze_intent_and_scope(state.user_input, state.attached_files, state.global_tier)
        state.intent = analysis["intent"]
        state.complexity = analysis.get("complexity", 5)
        state.analysis_results = analysis

        await state.narration_callback(
            f"Determined intent: {state.intent} (Complexity: {state.complexity}/10)",
            "decision",
        )
        return "gather_context"

class GatherContextNode(DAGNode):
    name = "gather_context"
    async def execute(self, state: TaskState, ctx: Any) -> str | None:
        await self._check_cancel(state)
        relevant_files = []
        if state.intent in ["question", "edit", "create", "debug"]:
            await state.narration_callback("Searching codebase for relevant context...", "info")
            relevant_files = ctx.repo_map.find_relevant_files(
                mentioned_files=state.analysis_results.get("mentioned_files", []),
                mentioned_symbols=state.analysis_results.get("mentioned_symbols", []),
            )
            if relevant_files:
                await state.narration_callback(
                    f"Found {len(relevant_files)} relevant files.", "result"
                )
                try:
                    import textual.app as _tapp

                    from src.core.events import FileRelevanceUpdated
                    _tapp.active_app.get().post_message(FileRelevanceUpdated(files=relevant_files))
                except Exception as e:
                    logger.debug(f"Could not post FileRelevanceUpdated to UI: {e}")
        state.relevant_files = relevant_files
        return "route_task"

class RouteTaskNode(DAGNode):
    name = "route_task"
    async def execute(self, state: TaskState, ctx: Any) -> str | None:
        await self._check_cancel(state)
        provider_family = None
        if ctx.mode_manager.active_mode.name.startswith("SINGLE_MODEL_"):
            provider_family = ctx.mode_manager.active_mode.value.replace("single_model_", "")

        selected_model = ctx.router.route_task(
            state.intent, state.complexity, state.global_tier, provider_family, role="orchestrator"
        )
        if state.model_selected_callback:
            await state.model_selected_callback("Orchestrator", selected_model.name)
        await state.narration_callback(
            f"Routed to {selected_model.name} based on complexity and tier.", "routing"
        )
        state.selected_model = selected_model
        return "prepare_blackboard"

class PrepareBlackboardNode(DAGNode):
    name = "prepare_blackboard"
    async def execute(self, state: TaskState, ctx: Any) -> str | None:
        await self._check_cancel(state)
        from src.core.workspace import Workspace
        ws = Workspace.get_instance()
        gptcgt_dir = ws.get_project_root() / ".gptcgt"
        if not (gptcgt_dir / "project.md").exists():
            from src.core.project_context import ProjectContextGenerator
            pcg = ProjectContextGenerator()
            pcg.generate_and_save()

        from src.core.blackboard import AgentBlackboard
        from src.core.task_brief import TaskBrief
        task_brief = TaskBrief(
            intent=state.intent,
            complexity=state.complexity,
            user_request=state.user_input[:500],
            mentioned_files=state.analysis_results.get("mentioned_files", []),
            mentioned_symbols=state.analysis_results.get("mentioned_symbols", []),
            selected_model_id=state.selected_model.id,
            selected_model_name=state.selected_model.name,
            quality_tier=state.global_tier.value,
        )
        bb = AgentBlackboard.get_instance()

        # Preserve specific blackboard state across 2-phase architect runs
        existing_plan = bb.read("architect_plan") if state.intent == "architect_execute" else None

        bb.clear()
        bb.write("task_brief", task_brief, author="orchestrator")
        bb.write("relevant_files", [str(f) for f in state.relevant_files], author="scout")

        if existing_plan:
            bb.write("architect_plan", existing_plan, author="architect")

        is_explicit_architect = (ctx.mode_manager.active_mode == OperationMode.ARCHITECT)
        state.is_architect_task = is_explicit_architect or (state.intent == "architect" and state.complexity >= 7)
        if state.is_architect_task:
            state.intent = "architect"
            return "architect_plan"

        if state.intent == "architect_execute":
            return "architect_execute"

        is_standard = (
            not state.is_architect_task
            and (
                ctx.mode_manager.active_mode in (
                    OperationMode.STANDARD,
                    OperationMode.SCOUT,
                ) or ctx.mode_manager.active_mode.name.startswith("SINGLE_MODEL_")
            )
        )
        if is_standard:
            return "standard_execution"
        else:
            return "parallel_execution"

class ArchitectPlanNode(DAGNode):
    name = "architect_plan"
    async def execute(self, state: TaskState, ctx: Any) -> str | None:
        await self._check_cancel(state)
        await state.narration_callback("🏗️ Architect Mode: Phase 1 — Generating plan...", "info")
        from src.core.chat_pipeline import ChatPipeline
        plan_pipeline = ChatPipeline(ctx.chat_store, state.global_tier)

        plan_text = ""
        async def capture_plan(chunk: str):
            nonlocal plan_text
            plan_text += chunk
            await state.yield_chunk_callback(chunk)

        provider_family = None
        if ctx.mode_manager.active_mode.name.startswith("SINGLE_MODEL_"):
            provider_family = ctx.mode_manager.active_mode.value.replace("single_model_", "")

        architect_model = ctx.router.route_task(
            state.intent, state.complexity, state.global_tier, provider_family, role="architect"
        )

        await plan_pipeline.process_message(
            user_text=(
                f"You are in ARCHITECT MODE (Phase 1: Planning Only).\n"
                f"Generate a detailed implementation plan for: {state.user_input}\n"
                f"Output ONLY the plan with numbered steps, files to modify, and rationale.\n"
                f"Do NOT write any code yet."
            ),
            attached_files=state.attached_files if state.attached_files else None,
            model_id_override=architect_model.id,
            yield_chunk_callback=capture_plan,
            tool_call_callback=state.tool_call_callback,
            thought_callback=state.thought_callback,
            error_callback=state.error_callback,
            cancel_event=state.cancel_event,
            complexity=state.complexity,
        )
        from src.core.blackboard import AgentBlackboard
        bb = AgentBlackboard.get_instance()
        bb.write("architect_plan", plan_text, author="architect")

        # Fire ArbiterVerdictReady to mount the UX gate
        from src.core.arbiter import ArbiterScore, ArbiterVerdict
        from src.core.events import ArbiterVerdictReady
        try:
            import textual.app as _tapp

            mock_score = ArbiterScore(
                agent_id="architect",
                model_name=architect_model.name,
                model_id=architect_model.id,
            )
            mock_verdict = ArbiterVerdict(
                dispatch_id="architect_plan",
                scores=[mock_score],
                winner=mock_score,
                runner_up=None,
                comparison_summary="Architect plan generated. Awaiting approval.",
                evidence=[],
                confidence="high",
            )
            _tapp.active_app.get().post_message(ArbiterVerdictReady(verdict=mock_verdict))
        except Exception as e:
            from src.core.logger import get_logger
            get_logger("core.dag").error(f"Failed to post architect verdict: {e}")

        # VERY IMPORTANT: Halt execution here. The UX Appoval Panel will create a new task
        # with SYSTEM_INTERNAL_CMD::EXECUTE_ARCHITECT_PLAN to resume.
        state.halt_execution = True
        return None

class ArchitectExecuteNode(DAGNode):
    name = "architect_execute"
    async def execute(self, state: TaskState, ctx: Any) -> str | None:
        await self._check_cancel(state)
        await state.narration_callback("🏗️ Architect Mode: Phase 2 — Executing plan...", "info")
        from src.core.blackboard import AgentBlackboard
        bb = AgentBlackboard.get_instance()
        plan_text = bb.read("architect_plan") or ""

        from src.core.chat_pipeline import ChatPipeline
        exec_pipeline = ChatPipeline(ctx.chat_store, state.global_tier)
        provider_family = None
        if ctx.mode_manager.active_mode.name.startswith("SINGLE_MODEL_"):
            provider_family = ctx.mode_manager.active_mode.value.replace("single_model_", "")

        coder_model = ctx.router.route_task(
            state.intent, state.complexity, state.global_tier, provider_family, role="coder"
        )

        await exec_pipeline.process_message(
            user_text=(
                f"You are in ARCHITECT MODE (Phase 2: Constrained Execution).\n"
                f"Execute ONLY the following approved plan — do not deviate:\n\n"
                f"{plan_text[:3000]}\n\n"
                f"Original request: {state.user_input}"
            ),
            attached_files=state.attached_files if state.attached_files else None,
            model_id_override=coder_model.id,
            yield_chunk_callback=state.yield_chunk_callback,
            tool_call_callback=state.tool_call_callback,
            thought_callback=state.thought_callback,
            error_callback=state.error_callback,
            cancel_event=state.cancel_event,
            complexity=state.complexity,
        )
        return "finalize"

class StandardExecutionNode(DAGNode):
    name = "standard_execution"
    async def execute(self, state: TaskState, ctx: Any) -> str | None:
        await self._check_cancel(state)
        await state.narration_callback(
            f"Executing task in {ctx.mode_manager.active_mode.name} mode...", "info"
        )
        from src.core.events import AgentStatusUpdate
        try:
            import textual.app as _tapp
            _tui_app = _tapp.active_app.get()
            _tui_app.post_message(AgentStatusUpdate(
                agent_id="orch", model_name=state.selected_model.name if state.selected_model else "AI",
                status="thinking", detail="Cross-referencing memory...",
            ))
        except Exception:
            pass

        from src.core.chat_pipeline import ChatPipeline
        pipeline = ChatPipeline(ctx.chat_store, state.global_tier)

        reflection_hint: str | None = None
        try:
            import textual.app as _tapp

            from src.tui.panels.chat import ChatPanel
            _chat = _tapp.active_app.get().query_one(ChatPanel)
            if _chat._pending_reflection_hint:
                reflection_hint = _chat._pending_reflection_hint
                _chat._pending_reflection_hint = None
        except Exception:
            pass

        response_text = ""
        async def intercept_yield(chunk: str):
            nonlocal response_text
            response_text += chunk
            await state.yield_chunk_callback(chunk)

        merged_files = list(state.attached_files) if state.attached_files else []
        if state.relevant_files:
            from src.core.workspace import Workspace
            ws = Workspace.get_instance()
            for rf in state.relevant_files[:10]:
                rf_path = str(rf)
                if not any(af.get("path") == rf_path for af in merged_files):
                    try:
                        content = ws.safe_read(rf_path)
                        if content:
                            merged_files.append({"path": rf_path, "content": content[:4000]})
                    except Exception:
                        pass

        # Dynamic role routing for execution nodes
        role = "coder"
        if ctx.mode_manager.active_mode == OperationMode.SCOUT:
            role = "scout"
        elif state.intent == "question":
            role = "orchestrator"

        provider_family = None
        if ctx.mode_manager.active_mode.name.startswith("SINGLE_MODEL_"):
            provider_family = ctx.mode_manager.active_mode.value.replace("single_model_", "")

        execution_model = ctx.router.route_task(
            state.intent, state.complexity, state.global_tier, provider_family, role=role
        )

        if state.model_selected_callback:
            # Tell the UI the actual execution role and model taking over
            await state.model_selected_callback(role.capitalize(), execution_model.name)

        await pipeline.process_message(
            user_text=state.user_input,
            attached_files=merged_files if merged_files else None,
            model_id_override=execution_model.id,
            yield_chunk_callback=intercept_yield,
            tool_call_callback=state.tool_call_callback,
            thought_callback=state.thought_callback,
            error_callback=state.error_callback,
            cancel_event=state.cancel_event,
            complexity=state.complexity,
            reflection_hint=reflection_hint,
        )

        state.final_response = response_text
        state.agent_texts["orch"] = response_text

        confusion_signals = [
            "I'm not sure", "I don't know", "I cannot determine",
            "I'm unable to", "beyond my capabilities",
        ]
        has_confusion_signal = any(sig.lower() in response_text.lower() for sig in confusion_signals)
        is_short = len(response_text.strip()) < 200
        # Require BOTH short AND confusion keyword; skip entirely for question intents
        is_confused = (
            is_short and has_confusion_signal
            and state.intent != "question"
        )
        if is_confused and state.global_tier != QualityTier.MAX:
            try:
                max_model = ctx.router.route_task(
                    state.intent, 10, QualityTier.MAX, role="coder",
                    provider_family=state.selected_model.provider.value if state.selected_model else None
                )
                if max_model.id != state.selected_model.id:
                    await state.narration_callback(f"⚡ Escalating to {max_model.name} (confusion detected)", "routing")
                    escalation_pipeline = ChatPipeline(ctx.chat_store, QualityTier.MAX)
                    await escalation_pipeline.process_message(
                        user_text=state.user_input,
                        attached_files=merged_files if merged_files else None,
                        model_id_override=max_model.id,
                        yield_chunk_callback=state.yield_chunk_callback,
                        tool_call_callback=state.tool_call_callback,
                        thought_callback=state.thought_callback,
                        error_callback=state.error_callback,
                        cancel_event=state.cancel_event,
                        complexity=10,
                        reflection_hint=reflection_hint,
                    )
            except Exception as esc_err:
                logger.debug(f"Escalation skipped: {esc_err}")

        return "finalize"

class ParallelExecutionNode(DAGNode):
    name = "parallel_execution"
    async def execute(self, state: TaskState, ctx: Any) -> str | None:
        await self._check_cancel(state)
        await state.narration_callback(f"Executing task in {ctx.mode_manager.active_mode.name} mode...", "info")
        import textual.app as _tapp

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

        _tui_app = _tapp.active_app.get()
        sandbox = E2BSandbox()
        ws = Workspace.get_instance()
        project_root = ws.get_project_root()
        security = SecurityScanner(project_root)
        lsp = LSPClient(project_root)
        arbiter = Arbiter(sandbox, security, lsp)
        dispatcher = ParallelDispatcher()

        count = 2 if ctx.mode_manager.active_mode == OperationMode.BATTLE else 3
        models = ctx.router.get_parallel_models(count)

        from src.core.system_prompt import SystemPromptBuilder
        sys_prompt = SystemPromptBuilder.build(model_name="orchestrator")
        context_messages = [{"role": "system", "content": sys_prompt}]
        for f in state.attached_files:
            context_messages.append({"role": "user", "content": f"File {f['path']}:\n{f['content']}"})
        context_messages.append({"role": "user", "content": state.user_input})

        from src.tools.tool_registry import get_tool_definitions
        tools = get_tool_definitions()

        if ctx.mode_manager.active_mode == OperationMode.ARCHITECT:
            from src.core.architect import ArchitectPipeline
            arch_pipeline = ArchitectPipeline(dispatcher, arbiter)
            event_stream = arch_pipeline.run_planning_phase(state.user_input, context_messages, models, tools)
        else:
            mode_str = "battle" if ctx.mode_manager.active_mode == OperationMode.BATTLE else "ensemble"
            event_stream = dispatcher.dispatch(state.user_input, context_messages, models, tools, mode=mode_str)

        current_dispatch_id = ""
        agent_texts = {}
        async for event in event_stream:
            await self._check_cancel(state)

            if event["type"] == "dispatch_started":
                current_dispatch_id = event["dispatch_id"]
                _tui_app.post_message(ParallelDispatchStarted(current_dispatch_id, ctx.mode_manager.active_mode.name, event["agents"]))  # noqa: E501
            elif event["type"] == "agent_chunk":
                agent_id = event["agent_id"]
                agent_texts[agent_id] = agent_texts.get(agent_id, "") + event["text"]
                _tui_app.post_message(MultiAgentChunk(dispatch_id=current_dispatch_id, agent_id=agent_id, text=event["text"]))  # noqa: E501
            elif event["type"] == "agent_tool_call":
                _tui_app.post_message(MultiAgentToolCall(dispatch_id=current_dispatch_id, agent_id=event["agent_id"], tool_name=event["tool_name"], args=event["args"]))  # noqa: E501
            elif event["type"] == "agent_complete":
                _tui_app.post_message(ParallelAgentComplete(dispatch_id=current_dispatch_id, agent_id=event["agent_id"], result={"duration_ms": event.get("duration_ms", 0), "cost_usd": event.get("cost_usd", 0.0)}))  # noqa: E501
            elif event["type"] == "error":
                if state.error_callback:
                    await state.error_callback(event.get("error", "Unknown error"))
            elif event["type"] == "all_complete":
                dispatch = event["dispatch"]
                _tui_app.post_message(ParallelDispatchComplete(dispatch))
                if ctx.mode_manager.active_mode != OperationMode.ARCHITECT:
                    await state.narration_callback("Running 6-stage Arbiter evaluation on patches...", "info")
                    async def on_progress(stage, agent_id, detail):
                        await state.narration_callback(f"Arbiter [{stage}]: {detail}", "decision")

                    verdict = await arbiter.evaluate(
                        dispatch, project_root,
                        ctx.workspace.config.project.primary_language or "python",
                        on_progress=on_progress, intent=state.intent
                    )
                    _tui_app.post_message(ArbiterVerdictReady(verdict))

                    from src.core.diff_engine import MultiAgentPatchSet
                    valid_patches = [s.patch_set for s in verdict.scores if s.patch_set and not s.eliminated]
                    if valid_patches:
                        multi_ps = MultiAgentPatchSet(patch_sets=valid_patches)
                        _tui_app.post_message(PatchSetProposed(patch_set=multi_ps))
            elif event["type"] == "arbiter_verdict":
                _tui_app.post_message(ArbiterVerdictReady(event["verdict"]))

        state.agent_texts.update(agent_texts)
        await lsp.shutdown_all()
        return "finalize"


class FinalizeNode(DAGNode):
    name = "finalize"
    async def execute(self, state: TaskState, ctx: Any) -> str | None:
        await self._check_cancel(state)
        for text in state.agent_texts.values():
            ctx._extract_annotations_from_response(text)
        await state.narration_callback("Task completed.", "result")
        return None
