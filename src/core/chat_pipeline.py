"""
Core chat pipeline that connects UI to LLM agents.
NOW WITH TOOL CALLING SUPPORT.

process_message() has been refactored into sub-methods for maintainability:
  _resolve_model()        -> ModelDefinition
  _resolve_api_credentials()  -> (api_key, base_url)
  _check_byok_daily_limit()   -> bool (should abort)
  _build_context_messages()   -> list[dict]
  _stream_agent_response()    -> str (full_response)
  _handle_post_stream()       -> None (cost recording, patch extraction)
"""

from __future__ import annotations

import json as _json

from src.billing.cost_breakdown import ModelUsage
from src.core.chat_store import ChatStore, MessageRole
from src.core.diff_engine import DiffExtractor
from src.core.logger import get_logger
from src.core.model_registry import ModelRegistry, QualityTier

logger = get_logger("core.pipeline")

# Map internal roles to LiteLLM-compatible roles
ROLE_TO_LITELLM = {
    "user": "user",
    "agent": "assistant",
    "orchestrator": "system",
    "arbiter": "assistant",
    "system": "system",
}


MAX_DELEGATION_DEPTH = 3
MAX_DELEGATION_TOKENS = 50000
MAX_DELEGATION_COST_USD = 0.50
MAX_DELEGATION_WALL_CLOCK_SEC = 120


class ChatPipeline:
    def __init__(self, chat_store: ChatStore, default_tier: QualityTier = QualityTier.STANDARD, _delegation_depth: int = 0):
        self.chat_store = chat_store
        self.default_tier = default_tier
        self.cost_tracker = None
        self.diff_extractor = DiffExtractor()
        self._delegation_depth = _delegation_depth
        try:
            import textual.app

            app = textual.app.active_app.get()
            if hasattr(app, "cost_tracker"):
                self.cost_tracker = app.cost_tracker
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  Public entry point                                                  #
    # ------------------------------------------------------------------ #

    async def process_message(
        self,
        user_text: str,
        attached_files: list[dict] | None = None,
        model_id_override: str | None = None,
        yield_chunk_callback=None,
        tool_call_callback=None,
        thought_callback=None,
        error_callback=None,
        cancel_event=None,
        complexity: int = 5,
        reflection_hint: str | None = None,
    ) -> None:
        # --- Lazy imports: loaded once per call, zero cost at app startup ---
        from src.agents.factory import PROVIDER_KEY_MAP, AgentFactory  # noqa: F401
        from src.auth.keychain import KeyChainManager
        from src.core.context_manager import ContextManager  # noqa: F401
        from src.core.system_prompt import SystemPromptBuilder
        from src.tools.tool_registry import get_tool_definitions
        # -------------------------------------------------------------------

        self.complexity = complexity
        registry = ModelRegistry()

        model_def, model_error = self._resolve_model(model_id_override, complexity)
        if model_error:
            if error_callback:
                await error_callback(model_error)
            return

        api_key, base_url = await self._resolve_api_credentials(
            model_def, KeyChainManager, PROVIDER_KEY_MAP, error_callback
        )
        if api_key is None and base_url is None:
            # _resolve_api_credentials already called error_callback
            return

        if await self._check_byok_daily_limit(base_url, error_callback):
            return

        agent = AgentFactory.create_agent(model_def, api_key=api_key, base_url=base_url)
        messages = self._build_context_messages(
            user_text, attached_files, reflection_hint, model_def, SystemPromptBuilder, ContextManager
        )

        total_usage = {"prompt_tokens": 0, "completion_tokens": 0}

        if self.cost_tracker:
            import uuid
            task_id = str(uuid.uuid4())
            self.cost_tracker.start_task(
                task_id=task_id,
                title=user_text[:50],
                mode="standard",
                tier=self.default_tier.value,
                credits=5,
            )

        agent.config.tools = get_tool_definitions()
        agent.config.temperature = 0.2
        if self.default_tier == QualityTier.LIGHT:
            agent.config.max_tokens = 1000

        try:
            full_response = await self._stream_agent_response(
                agent=agent,
                messages=messages,
                model_def=model_def,
                user_text=user_text,
                total_usage=total_usage,
                yield_chunk_callback=yield_chunk_callback,
                tool_call_callback=tool_call_callback,
                thought_callback=thought_callback,
                error_callback=error_callback,
                cancel_event=cancel_event,
            )
            await self._handle_post_stream(full_response, model_def, user_text, total_usage, registry)
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            if error_callback:
                await error_callback(str(e))

    # ------------------------------------------------------------------ #
    #  Private sub-methods                                                 #
    # ------------------------------------------------------------------ #

    def _resolve_model(self, model_id_override, complexity) -> tuple:
        """Resolve ModelDefinition from override or router. Returns (model_def, error_str)."""
        registry = ModelRegistry()
        try:
            if model_id_override:
                model_def = registry.get(model_id_override)
                if not model_def:
                    logger.warning(f"Target model '{model_id_override}' not found in registry.")
                    return None, f"Requested model '{model_id_override}' is not registered. Check the model ID."
            else:
                from src.core.router import CodingRouter
                model_def = CodingRouter().route_task("chat", complexity, self.default_tier, role="coder")
        except ValueError as e:
            return None, str(e)

        if not model_def:
            return None, "Could not resolve a model specification."
        return model_def, None

    async def _resolve_api_credentials(self, model_def, KeyChainManager, PROVIDER_KEY_MAP, error_callback):
        """Return (api_key, base_url). Returns (None, None) and calls error_callback on failure."""
        # Check auth manager for proxy routing
        auth_manager = None
        try:
            import textual.app as _tapp
            current_app = _tapp.active_app.get()
            if hasattr(current_app, "auth_manager"):
                auth_manager = current_app.auth_manager
        except Exception:
            pass

        if auth_manager and auth_manager.use_managed_credits:
            access, _ = KeyChainManager.get_auth_tokens()
            if not access:
                if error_callback:
                    await error_callback(
                        "Authentication token missing for managed credits. Please sign in again."
                    )
                return None, None
            return access, "https://api.gptcgt.ai/proxy/v1"

        key_name = PROVIDER_KEY_MAP.get(model_def.provider.value)
        api_key = KeyChainManager.get_key(key_name) if key_name else None
        if key_name and not api_key:
            if error_callback:
                await error_callback(f"Missing API key for {model_def.provider.value}.")
            return None, None
        return api_key, None

    async def _check_byok_daily_limit(self, base_url, error_callback) -> bool:
        """Return True if the daily BYOK limit has been reached (should abort pipeline)."""
        if base_url:
            # Managed credits path — no local limit to check
            return False
        if not self.cost_tracker:
            return False
        try:
            from src.core.config import ConfigManager
            config = ConfigManager()
            limit = config.user.daily_spend_limit
            today_spend = self.cost_tracker.get_today_spend().total_cost
            if limit is not None and limit > 0 and today_spend >= limit:
                msg = (
                    f"💳 BYOK Spending Cap Reached: You have spent ${today_spend:.2f} today, "
                    f"exceeding your local limit of ${limit:.2f}. "
                    "Please adjust your settings to continue."
                )
                if error_callback:
                    await error_callback(msg)
                return True
        except Exception as e:
            logger.error(f"Failed to check BYOK spending limits: {e}")
        return False

    def _build_context_messages(
        self, user_text, attached_files, reflection_hint, model_def, SystemPromptBuilder, ContextManager
    ) -> list[dict]:
        """Assemble system prompt + history + reflection hint into a message list."""
        context_mgr = ContextManager(model_def.id)
        history = self.chat_store.get_recent_messages(count=50)

        system_prompt = SystemPromptBuilder.build(model_name=model_def.name)

        history_dicts = []
        for m in history:
            d = m.to_dict()
            d["role"] = ROLE_TO_LITELLM.get(d["role"], "user")
            history_dicts.append(d)

        # Inject reflection lesson if present (from ReflectionEngine via ChatPanel)
        effective_system_prompt = system_prompt
        if reflection_hint:
            effective_system_prompt = (
                system_prompt
                + f"\n\n## Memory Update (Reflection Engine)\n{reflection_hint}"
            )
            logger.info("Injected ReflectionEngine lesson into system context.")

        return context_mgr.prepare_payload(
            system_prompt=effective_system_prompt,
            history_messages=history_dicts,
            new_user_message=user_text,
            attached_files=attached_files,
        )

    async def _stream_agent_response(
        self,
        agent,
        messages,
        model_def,
        user_text,
        total_usage,
        yield_chunk_callback,
        tool_call_callback,
        thought_callback,
        error_callback,
        cancel_event,
    ) -> str:
        """Run the agent stream loop including tool calling, self-healing, and swarm handoffs."""
        full_response = ""
        healing_attempts = 0

        while True:
            iteration_text = ""
            tool_calls = []

            async for chunk in agent.chat_stream(messages):
                if cancel_event and cancel_event.is_set():
                    import asyncio
                    self._trigger_reflection_on_abort(model_def.name, user_text, iteration_text)
                    raise asyncio.CancelledError("User pressed Panic Button during generation.")

                if chunk.text:
                    iteration_text += chunk.text
                    full_response += chunk.text
                    if yield_chunk_callback:
                        await yield_chunk_callback(chunk.text)
                if chunk.usage:
                    total_usage["prompt_tokens"] += chunk.usage.get("prompt_tokens", 0)
                    total_usage["completion_tokens"] += chunk.usage.get("completion_tokens", 0)
                if chunk.tool_calls:
                    tool_calls = chunk.tool_calls

            if not tool_calls:
                should_retry, full_response, healing_attempts = await self._handle_self_healing(
                    full_response,
                    model_def.name,
                    healing_attempts,
                    messages,
                    yield_chunk_callback,
                    complexity=self.complexity,
                )
                if should_retry:
                    continue
                break

            cmd_msgs = await self._execute_tools(tool_calls, tool_call_callback, thought_callback)
            full_response, did_delegate = await self._handle_handoff(
                cmd_msgs, full_response, yield_chunk_callback,
                tool_call_callback, thought_callback, error_callback, cancel_event
            )
            if did_delegate:
                break

            messages.append({
                "role": "assistant",
                "content": iteration_text if iteration_text else None,
                "tool_calls": tool_calls,
            })
            messages.extend(cmd_msgs)

        return full_response

    def _trigger_reflection_on_abort(self, model_name: str, user_text: str, iteration_text: str) -> None:
        """Fire-and-forget: spawn ReflectionEngine on user abort."""
        try:
            import textual.app as _tapp
            from src.core.reflection_engine import ReflectionEngine
            engine = ReflectionEngine(_tapp.active_app.get())
            engine.reflect_on_friction(
                model_name=model_name,
                trigger_event="USER_ABORT",
                original_prompt=user_text,
                agent_output=iteration_text,
                failure_reason="User manually halted the generation stream.",
            )
        except Exception:
            pass

    async def _handle_handoff(
        self, cmd_msgs, full_response, yield_chunk_callback,
        tool_call_callback, thought_callback, error_callback, cancel_event
    ):
        """Check for swarm delegation handoff signal in tool results. Returns (response, did_delegate)."""
        handoff_payload = None
        for msg in cmd_msgs:
            if msg.get("role") == "tool":
                try:
                    data = _json.loads(msg.get("content", ""))
                    if isinstance(data, dict) and data.get("__handoff_signal__"):
                        handoff_payload = data
                        break
                except Exception:
                    continue

        if not handoff_payload:
            return full_response, False

        target_id = handoff_payload.get("target_agent_id", "openai/gpt-4o-mini")
        instruction = handoff_payload.get("instruction", "")
        action = handoff_payload.get("action", "consult")
        files = handoff_payload.get("files", [])

        # P0 Fix: Recursion depth guard
        if self._delegation_depth >= MAX_DELEGATION_DEPTH:
            logger.warning(f"Delegation depth {self._delegation_depth} exceeds max {MAX_DELEGATION_DEPTH}. Aborting sub-dispatch.")
            if error_callback:
                await error_callback(f"Delegation depth limit ({MAX_DELEGATION_DEPTH}) reached. Recursive handoff aborted.")
            return full_response, False

        # Multi-budget guard: check accumulated cost and tokens
        if self.cost_tracker:
            try:
                today = self.cost_tracker.get_today_spend()
                accumulated = today.total_cost
                if accumulated >= MAX_DELEGATION_COST_USD:
                    logger.warning(f"Delegation cost cap reached: ${accumulated:.4f} >= ${MAX_DELEGATION_COST_USD}")
                    if error_callback:
                        await error_callback(f"Delegation cost limit (${MAX_DELEGATION_COST_USD:.2f}) reached.")
                    return full_response, False
            except Exception:
                pass

        # P0 Fix: Read file content so ContextManager gets {"path": ..., "content": ...}
        attached_files_with_content = None
        if files:
            attached_files_with_content = []
            try:
                from src.core.workspace import Workspace
                ws = Workspace.get_instance()
                for f in files:
                    content = ws.safe_read(f) if ws.safe_exists(f) else ""
                    attached_files_with_content.append({"path": f, "content": content})
            except Exception as e:
                logger.warning(f"Failed to read handoff files: {e}")
                attached_files_with_content = [{"path": f, "content": ""} for f in files]

        import time
        start_handoff = time.monotonic()
        sub_pipeline = ChatPipeline(self.chat_store, self.default_tier, _delegation_depth=self._delegation_depth + 1)
        child_response_chunks: list[str] = []

        async def sub_chunk_catcher(text: str, _chunks: list = child_response_chunks):
            _chunks.append(text)
            # Enforce token cap: estimate tokens from accumulated text
            total_chars = sum(len(c) for c in _chunks)
            if total_chars // 4 > MAX_DELEGATION_TOKENS:
                raise RuntimeError(f"Delegation token cap ({MAX_DELEGATION_TOKENS}) exceeded.")
            # Enforce wall-clock cap
            if time.monotonic() - start_handoff > MAX_DELEGATION_WALL_CLOCK_SEC:
                raise RuntimeError(f"Delegation wall-clock cap ({MAX_DELEGATION_WALL_CLOCK_SEC}s) exceeded.")
            if yield_chunk_callback:
                await yield_chunk_callback(text)

        try:
            await sub_pipeline.process_message(
                user_text=instruction,
                attached_files=attached_files_with_content,
                model_id_override=target_id,
                yield_chunk_callback=sub_chunk_catcher,
                tool_call_callback=tool_call_callback,
                thought_callback=thought_callback,
                error_callback=error_callback,
                cancel_event=cancel_event,
                complexity=self.complexity,
            )
        except RuntimeError as budget_err:
            logger.warning(f"Delegation budget exceeded: {budget_err}")
            if error_callback:
                await error_callback(str(budget_err))

        child_full_text = "".join(child_response_chunks)
        elapsed = time.monotonic() - start_handoff

        if thought_callback:
            await thought_callback(
                f"Swarm Handoff: {target_id} ({elapsed:.1f}s)",
                f"Instruction:\n{instruction}\n\nResult:\n{child_full_text}"
            )

        if action == "delegate":
            return full_response + f"\n\n[Delegated to {target_id}]:\n{child_full_text}", True

        cmd_msgs.append({"role": "user", "content": f"[Result from {target_id}]:\n{child_full_text}"})
        return full_response, False

    async def _handle_post_stream(self, full_response, model_def, user_text, total_usage, registry) -> None:
        """Persist chat history, record cost, and post PatchSetProposed event."""
        self.chat_store.add_message(
            MessageRole.USER, user_text, tokens_used=total_usage["prompt_tokens"]
        )
        self.chat_store.add_message(
            MessageRole.AGENT,
            full_response,
            model_id=model_def.id,
            tokens_used=total_usage["completion_tokens"],
            cost=registry.calculate_cost(
                model_def.id, total_usage["prompt_tokens"], total_usage["completion_tokens"]
            ),
        )

        if self.cost_tracker:
            cost = registry.calculate_cost(
                model_def.id, total_usage["prompt_tokens"], total_usage["completion_tokens"]
            )
            self.cost_tracker.record_model_usage(
                ModelUsage(
                    model_id=model_def.id,
                    model_display_name=model_def.name,
                    provider=model_def.provider.value,
                    role="Standard",
                    input_tokens=total_usage["prompt_tokens"],
                    output_tokens=total_usage["completion_tokens"],
                    input_cost=(total_usage["prompt_tokens"] / 1000000) * model_def.input_cost_per_mtok,
                    output_cost=(total_usage["completion_tokens"] / 1000000) * model_def.output_cost_per_mtok,
                    total_cost=cost,
                )
            )
            self.cost_tracker.finish_task()

        patch_set = self.diff_extractor.extract(
            full_response, agent_id="orchestrator", model_name=model_def.name
        )
        if patch_set.file_count > 0:
            try:
                import textual.app as _tapp
                from src.core.events import PatchSetProposed
                _tapp.active_app.get().post_message(PatchSetProposed(patch_set=patch_set))
            except Exception as e:
                logger.debug(f"Could not post PatchSetProposed: {e}")

        # Proactive success logging: record routing + cost for learning
        try:
            import textual.app as _tapp
            _app = _tapp.active_app.get()
            from src.core.reflection_engine import ReflectionEngine
            engine = ReflectionEngine(_app)
            cost = registry.calculate_cost(
                model_def.id, total_usage["prompt_tokens"], total_usage["completion_tokens"]
            )
            engine.log_success(
                model_name=model_def.name,
                model_id=model_def.id,
                tier=self.default_tier.value,
                cost_usd=cost,
                input_tokens=total_usage["prompt_tokens"],
                output_tokens=total_usage["completion_tokens"],
            )
        except Exception as e:
            logger.debug(f"Proactive logging skipped: {e}")

    async def _handle_self_healing(
        self,
        full_response: str,
        model_name: str,
        healing_attempts: int,
        messages: list,
        yield_chunk_callback,
        complexity: int = 5,
    ) -> tuple[bool, str, int]:
        """Runs conditional E2B sandbox verification on proposed patches."""
        patch_set = self.diff_extractor.extract(
            full_response, agent_id="orchestrator", model_name=model_name
        )
        if patch_set.file_count > 0:
            from src.core.workspace import Workspace
            from src.tools.sandbox import E2BSandbox

            sandbox = E2BSandbox()
            should_verify = sandbox.available and healing_attempts < 2 and complexity > 4

            if should_verify:
                ws = Workspace.get_instance()
                verdict = await sandbox.verify_patch(patch_set, ws.get_project_root(), "python")
                if not verdict.tests_passed and verdict.test_failures:
                    healing_attempts += 1
                    if yield_chunk_callback:
                        await yield_chunk_callback(
                            "\n\n[Tests Failed] 🔄 Self-healing retry initiated...\n"
                        )
                    messages.append({"role": "assistant", "content": full_response})
                    messages.append({
                        "role": "user",
                        "content": (
                            f"The test sandbox failed with the following errors upon running your code. "
                            f"Please fix them:\n{verdict.test_failures[0]}\nGenerate the corrected code."
                        ),
                    })
                    return True, "", healing_attempts
        return False, full_response, healing_attempts

    async def _execute_tools(self, tool_calls: list, tool_call_callback, thought_callback) -> list[dict]:
        """Executes LLM requested functions mapping JSON outputs natively."""
        import time
        cmd_msgs = []
        for tc in tool_calls:
            from src.tools.tool_registry import execute_tool

            fn_name = tc.get("function", {}).get("name", tc.get("name"))
            args_raw = tc.get("function", {}).get("arguments", tc.get("arguments", "{}"))
            try:
                fn_args = _json.loads(args_raw)
            except _json.JSONDecodeError:
                fn_args = {}

            if tool_call_callback:
                await tool_call_callback(fn_name, fn_args)

            start_t = time.monotonic()
            result = execute_tool(fn_name, fn_args)
            elapsed = time.monotonic() - start_t

            if thought_callback:
                await thought_callback(
                    f"Executed `{fn_name}` tool ({elapsed:.1f}s)",
                    f"Arguments:\n{args_raw}\n\nResult:\n{result}"
                )

            cmd_msgs.append(
                {"role": "tool", "name": fn_name, "tool_call_id": tc.get("id"), "content": result}
            )
        return cmd_msgs
