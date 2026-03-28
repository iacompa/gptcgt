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
from src.core.endpoints import resolve_terminal_proxy_url
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
    def __init__(
        self, chat_store: ChatStore, default_tier: QualityTier = QualityTier.STANDARD, _delegation_depth: int = 0
    ):  # noqa: E501
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

        # Spending cap preflight: hard-stop before any API call
        if self.cost_tracker:
            try:
                from src.billing.spending_caps import SpendingCapService

                SpendingCapService()
                today_spend = self.cost_tracker.get_today_spend()
                if today_spend.total_cost >= MAX_DELEGATION_COST_USD * 10:  # User-level daily cap
                    if error_callback:
                        await error_callback(
                            f"⛔ Spending Cap exceeded (${today_spend.total_cost:.2f} today). "
                            "Adjust your spending cap in Settings or wait until tomorrow."
                        )
                    return
            except Exception:
                pass  # Non-blocking if billing service is unavailable

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

        # Fetch active mode for proxy accounting headers
        current_mode = "standard"
        try:
            import textual.app as _tapp

            current_mode = _tapp.active_app.get().orchestrator.mode_manager.active_mode.value
        except Exception:
            pass

        extra_headers = {"X-GPTCGT-Mode": current_mode}
        agent = AgentFactory.create_agent(model_def, api_key=api_key, base_url=base_url, extra_headers=extra_headers)
        messages = await self._build_context_messages(
            user_text, attached_files, reflection_hint, model_def, SystemPromptBuilder, ContextManager
        )

        total_usage = {"prompt_tokens": 0, "completion_tokens": 0}

        if self.cost_tracker:
            import uuid

            task_id = str(uuid.uuid4())
            # F21: Use actual mode and credit cost instead of hardcoded standard/5
            from src.billing.credits import CreditService

            _credit_svc = CreditService()
            _actual_mode = current_mode if current_mode else "standard"
            _actual_credits = _credit_svc.CREDIT_COSTS.get(_actual_mode, 5)
            self.cost_tracker.start_task(
                task_id=task_id,
                title=user_text[:50],
                mode=_actual_mode,
                tier=self.default_tier.value,
                credits=_actual_credits,
            )

        agent.config.tools = get_tool_definitions()
        agent.config.temperature = 0.2

        # ── Phase 4+5: CostAutopilot mode selection + policy enforcement ──
        from src.core.config import ConfigManager
        usr_cfg = ConfigManager.get_instance().user

        # Build budget health from cost tracker
        autopilot_decision = None
        try:
            from src.core.autopilot import BudgetHealth, CostAutopilot

            budget_health = BudgetHealth(
                daily_limit_usd=getattr(usr_cfg, "daily_spend_limit", 10.0),
                session_limit_usd=getattr(usr_cfg, "max_autonomous_budget", 20.0),
            )
            if self.cost_tracker:
                today = self.cost_tracker.get_today_spend()
                budget_health.daily_spend_usd = today.total_cost

            autopilot = CostAutopilot()
            autopilot_decision = autopilot.select_mode(complexity, budget_health)
            logger.info(f"Autopilot: {autopilot_decision.to_text()}")
        except Exception as e:
            logger.debug(f"Autopilot skipped: {e}")

        # Policy run-start check
        try:
            from src.core.policy import PolicyEnforcer, PolicyParser
            policy_cfg, _ = PolicyParser.load()
            enforcer = PolicyEnforcer(policy_cfg)
            current_spend = 0.0
            if self.cost_tracker:
                current_spend = self.cost_tracker.get_today_spend().total_cost
            allowed, errs = enforcer.check_run_start(current_spend, current_mode)
            if not allowed:
                logger.warning(f"Policy blocked run start: {errs}")
                if error_callback:
                    await error_callback(f"⛔ Policy violation: {'; '.join(errs)}")
                return
        except Exception as e:
            logger.debug(f"Policy run-start check skipped: {e}")

        # Apply token limits from autopilot decision or static config
        if current_mode == "architect":
            agent.config.max_tokens = getattr(usr_cfg, "max_tokens_architect", 3000)
        elif current_mode == "coder":
            agent.config.max_tokens = getattr(usr_cfg, "max_tokens_coder", 8000)
        elif current_mode == "scout":
            agent.config.max_tokens = getattr(usr_cfg, "max_tokens_scout", 2000)
        elif current_mode == "tester":
            agent.config.max_tokens = getattr(usr_cfg, "max_tokens_tester", 4000)
        else:
            agent.config.max_tokens = getattr(usr_cfg, "max_tokens_default", 5000)

        # Override with autopilot ceiling if lower
        if autopilot_decision:
            autopilot_cap = autopilot_decision.budget.max_tokens_output
            if autopilot_cap < agent.config.max_tokens:
                agent.config.max_tokens = autopilot_cap
                logger.info(f"Autopilot capped tokens to {autopilot_cap}")
        # ──────────────────────────────────────────────────────────────────

        try:
            MAX_FAILOVER_ATTEMPTS = 2
            failed_models: set[str] = set()
            current_model = model_def

            for attempt in range(MAX_FAILOVER_ATTEMPTS + 1):
                try:
                    full_response = await self._stream_agent_response(
                        agent=agent,
                        messages=messages,
                        model_def=current_model,
                        user_text=user_text,
                        total_usage=total_usage,
                        yield_chunk_callback=yield_chunk_callback,
                        tool_call_callback=tool_call_callback,
                        thought_callback=thought_callback,
                        error_callback=error_callback,
                        cancel_event=cancel_event,
                    )
                    break  # Success
                except Exception as stream_err:
                    from src.agents.base import ProviderException

                    # noqa: W293
                    is_transient = False
                    is_auth = False
                    # noqa: W293
                    if isinstance(stream_err, ProviderException):
                        if stream_err.error_type in ("rate_limit", "timeout", "unknown"):
                            is_transient = True
                        elif stream_err.error_type == "auth_error":
                            is_auth = True
                    else:
                        err_str = str(stream_err).lower()
                        is_transient = any(
                            kw in err_str
                            for kw in (
                                "rate limit",
                                "rate_limit",
                                "ratelimit",
                                "429",
                                "timeout",
                                "timed out",
                                "connection",
                                "temporary",
                                "503",
                                "502",
                                "overloaded",
                            )
                        )
                        is_auth = any(
                            kw in err_str
                            for kw in (
                                "auth",
                                "401",
                                "403",
                                "invalid api key",
                                "invalid_api_key",
                                "unauthorized",
                            )
                        )

                    if is_auth or not is_transient or attempt == MAX_FAILOVER_ATTEMPTS:
                        raise stream_err

                    failed_models.add(current_model.id)
                    fallback = registry.get_fallback_model(
                        current_model.id,
                        self.default_tier,
                        provider_preference=current_model.provider.value,
                        excluded=failed_models,
                    )
                    if not fallback:
                        raise

                    logger.warning(
                        f"Failover: {current_model.name} failed ({stream_err}), retrying with {fallback.name}"
                    )
                    try:
                        import textual.app as _tapp  # noqa: I001
                        from src.core.events import OrchestratorNarration

                        app = _tapp.active_app.get()
                        app.post_message(
                            OrchestratorNarration(
                                f"⚠️ {current_model.name} failed, retrying with {fallback.name}...",
                                "warning",
                            )
                        )
                    except Exception:
                        pass

                    current_model = fallback
                    fb_key, fb_url = await self._resolve_api_credentials(
                        current_model, KeyChainManager, PROVIDER_KEY_MAP, error_callback
                    )
                    if fb_key is None and fb_url is None:
                        raise
                    agent = AgentFactory.create_agent(
                        current_model,
                        api_key=fb_key,
                        base_url=fb_url,
                        extra_headers=extra_headers,
                    )
                    agent.config.tools = get_tool_definitions()
                    agent.config.temperature = 0.2

            await self._handle_post_stream(full_response, current_model, user_text, total_usage, registry)
        except Exception as e:
            from src.agents.base import ProviderException

            # noqa: W293
            # Guarantee the UI spinner stops on a hard pipeline crash
            try:
                import textual.app as _tapp  # noqa: I001
                from src.core.events import AgentCompleted

                app = _tapp.active_app.get()
                app.post_message(AgentCompleted())
            except Exception:
                pass

            if isinstance(e, ProviderException):
                logger.error(f"Provider error ({e.provider} - {e.error_type}): {e.message}")
                if error_callback:
                    await error_callback(f"Provider Error: {e.message}")
            else:
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
                    parts = model_id_override.split("/", 1)
                    if len(parts) == 2:
                        provider_str, model_name = parts
                        from src.core.model_registry import Provider

                        try:
                            valid_provider = Provider(provider_str)
                            logger.info(f"Synthesizing temporary ModelDefinition for {model_id_override}")
                            from src.core.model_registry import ModelDefinition

                            model_def = ModelDefinition(
                                id=model_id_override,
                                name=model_name.replace("-", " ").title(),
                                provider=valid_provider,
                                input_cost_per_mtok=0.0,
                                output_cost_per_mtok=0.0,
                                max_context_tokens=128000,
                                max_output_tokens=8192,
                                quality_tiers=["standard"],
                            )
                        except ValueError:
                            return (
                                None,
                                f"Unsupported provider '{provider_str}' in model override '{model_id_override}'.",
                            )  # noqa: E501
                    else:
                        return None, f"Malformed model ID '{model_id_override}'. Expected 'provider/model' format."
            else:
                # Phase 9: Auto-tiering — let complexity score pick the tier
                effective_tier = self.default_tier
                try:
                    import textual.app as _tapp

                    current_app = _tapp.active_app.get()
                    if hasattr(current_app, "orchestrator"):
                        mm = current_app.orchestrator.mode_manager
                        if mm.can_auto_tier():
                            recommended = mm.recommend_tier(complexity)
                            if recommended != effective_tier:
                                tier_labels = {
                                    "light": "💡 Light (fast)",
                                    "standard": "⚡ Standard",
                                    "max": "🔥 Max (reasoning)",
                                }  # noqa: E501
                                label = tier_labels.get(recommended.value, recommended.value)  # noqa: F841
                                logger.info(f"Auto-tiering: complexity {complexity}/10 → {recommended.value}")
                                effective_tier = recommended
                except Exception as e:
                    logger.debug(f"Auto-tiering skipped: {e}")

                from src.core.router import CodingRouter

                model_def = CodingRouter().route_task("chat", complexity, effective_tier, role="coder")
        except ValueError as e:
            return None, str(e)

        if not model_def:
            return None, "Could not resolve a model specification."
        return model_def, None

    async def _resolve_api_credentials(self, model_def, KeyChainManager, provider_key_map=None, error_callback=None):
        """Return (api_key, base_url). Returns (None, None) and calls error_callback on failure."""
        if provider_key_map is None:
            try:
                from src.agents.factory import PROVIDER_KEY_MAP

                provider_key_map = PROVIDER_KEY_MAP
            except Exception:
                provider_key_map = {}

        async def _emit_error(message: str) -> None:
            if error_callback is None:
                return
            result = error_callback(message)
            if hasattr(result, "__await__"):
                await result

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
                await _emit_error("Authentication token missing for managed credits. Please sign in again.")
                return None, None
            return access, resolve_terminal_proxy_url()

        key_name = provider_key_map.get(model_def.provider.value)
        api_key = KeyChainManager.get_key(key_name) if key_name else None
        # noqa: W293
        # Extract explicitly defined base_url for custom/local endpoints
        base_url = getattr(model_def, "base_url", None)
        # noqa: W293
        # Strict validation of base_url
        if base_url:
            import urllib.parse

            try:
                res = urllib.parse.urlparse(base_url)
                if res.scheme not in ("http", "https") or not res.netloc:
                    await _emit_error(
                        f"Invalid custom base_url: '{base_url}'. Must include valid scheme (http/https) and host."
                    )  # noqa: E501
                    return None, None
            except Exception:
                await _emit_error(f"Malformed custom base_url: '{base_url}'")
                return None, None

        if key_name and not api_key:
            from src.core.model_registry import Provider

            # noqa: W293
            # If CUSTOM provider and it explicitly says api_key_required=False, allow it.
            if model_def.provider == Provider.CUSTOM:
                if not getattr(model_def, "api_key_required", False):
                    return None, base_url
                else:
                    await _emit_error(
                        f"Missing API key for custom endpoint '{model_def.id}'. Either provide a key, or set 'api_key_required = false' in your config."
                    )  # noqa: E501
                    return None, None
            # noqa: W293
            # Normal provider failure
            await _emit_error(f"Missing API key for {model_def.provider.value}.")
            return None, None
        # noqa: W293
        return api_key, base_url

    async def _check_byok_daily_limit(self, base_url, error_callback) -> bool:
        """Return True if the daily BYOK limit has been reached (should abort pipeline)."""
        if base_url:
            # Managed credits path — no local limit to check
            return False
        if not self.cost_tracker:
            return False
        try:
            from src.core.config import ConfigManager

            config = ConfigManager.get_instance()
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

    async def _build_context_messages(
        self, user_text, attached_files, reflection_hint, model_def, SystemPromptBuilder, ContextManager
    ) -> list[dict]:
        """
        Assemble system prompt + history + reflection hint into a message list.  # noqa: D213

        Uses ContextCompactor for semantic summarization of old messages
        before ContextManager applies hard token budget truncation.
        """
        context_mgr = ContextManager(model_def.id)
        history = self.chat_store.get_recent_messages(count=50)

        system_prompt = SystemPromptBuilder.build(model_name=model_def.name)

        # --- Semantic compaction layer ---
        # Summarize old messages so ContextManager has less to truncate
        from src.core.context_compactor import ContextCompactor

        compactor = ContextCompactor(max_tokens=getattr(model_def, "max_context_tokens", 100_000))
        keep_full = 20  # keep last 20 messages at full fidelity
        compacted_history = list(history)
        summary_prefix = []

        conversational = [m for m in history if m.role.value in ("user", "agent")]
        if len(conversational) > keep_full:
            to_summarize = conversational[:-keep_full]
            summary_text = await compactor._summarize_old_messages(to_summarize)
            if summary_text:
                summary_prefix = [{"role": "user", "content": f"[Earlier summary: {summary_text}]"}]
            # Keep only recent messages for the history_dicts
            summarized_ids = {id(m) for m in to_summarize}
            compacted_history = [m for m in history if id(m) not in summarized_ids]

        history_dicts = []
        for m in compacted_history:
            d = m.to_dict()
            d["role"] = ROLE_TO_LITELLM.get(d["role"], "user")
            history_dicts.append(d)

        # Prepend summary if we compacted
        if summary_prefix:
            history_dicts = summary_prefix + history_dicts

        # Inject per-agent persistent memory (past lessons learned)
        effective_system_prompt = system_prompt
        try:
            from src.core.memory import AgentMemory
            from src.core.workspace import Workspace

            ws = Workspace.get_instance()
            agent_mem = AgentMemory(ws.get_project_root())
            agent_context = agent_mem.get_context(model_def.name)
            if agent_context:
                effective_system_prompt += f"\n\n{agent_context}"
                logger.info(f"Injected {len(agent_context)} chars of agent memory into prompt.")
        except Exception as e:
            logger.debug(f"Agent memory injection skipped: {e}")

        # Inject reflection lesson if present (from ReflectionEngine via ChatPanel)
        if reflection_hint:
            effective_system_prompt = (
                effective_system_prompt + f"\n\n## Memory Update (Reflection Engine)\n{reflection_hint}"
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
                cmd_msgs,
                full_response,
                yield_chunk_callback,
                tool_call_callback,
                thought_callback,
                error_callback,
                cancel_event,
            )
            if did_delegate:
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": iteration_text if iteration_text else None,
                    "tool_calls": tool_calls,
                }
            )
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
                task_id="abort_event",
            )
        except Exception:
            pass

    async def _handle_handoff(
        self,
        cmd_msgs,
        full_response,
        yield_chunk_callback,
        tool_call_callback,
        thought_callback,
        error_callback,
        cancel_event,
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
            logger.warning(
                f"Delegation depth {self._delegation_depth} exceeds max {MAX_DELEGATION_DEPTH}. Aborting sub-dispatch."
            )  # noqa: E501
            if error_callback:
                await error_callback(
                    f"Delegation depth limit ({MAX_DELEGATION_DEPTH}) reached. Recursive handoff aborted."
                )  # noqa: E501
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

        try:
            import textual.app

            from src.core.events import SubTaskDelegated

            # We don't have the explicit parent ID inside the nested pipeline, so we use 'Orchestrator' or previous agent  # noqa: E501
            _tui_app = textual.app.active_app.get()
            _tui_app.post_message(
                SubTaskDelegated(
                    parent_agent_id="agent",
                    child_model_name=target_id,
                    instruction=instruction,
                    depth=self._delegation_depth + 1,
                )
            )
        except Exception:
            pass

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
                raise RuntimeError(f"Delegation wall-clock cap ({MAX_DELEGATION_WALL_CLOCK_SEC}) exceeded.")
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
                f"Instruction:\n{instruction}\n\nResult:\n{child_full_text}",
            )

        if action == "delegate":
            return full_response + f"\n\n[Delegated to {target_id}]:\n{child_full_text}", True

        cmd_msgs.append({"role": "user", "content": f"[Result from {target_id}]:\n{child_full_text}"})
        return full_response, False

    async def _handle_post_stream(self, full_response, model_def, user_text, total_usage, registry) -> None:
        """Persist chat history, record cost, and post PatchSetProposed event."""
        self.chat_store.add_message(MessageRole.USER, user_text, tokens_used=total_usage["prompt_tokens"])
        self.chat_store.add_message(
            MessageRole.AGENT,
            full_response,
            model_id=model_def.id,
            tokens_used=total_usage["completion_tokens"],
            cost=registry.calculate_cost(model_def.id, total_usage["prompt_tokens"], total_usage["completion_tokens"]),
        )

        if self.cost_tracker:
            cost = registry.calculate_cost(model_def.id, total_usage["prompt_tokens"], total_usage["completion_tokens"])
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

            # Phase 9: Per-task budget enforcement
            self._check_task_budget(cost, total_usage, model_def)

        patch_set = self.diff_extractor.extract(full_response, agent_id="orchestrator", model_name=model_def.name)
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
            cost = registry.calculate_cost(model_def.id, total_usage["prompt_tokens"], total_usage["completion_tokens"])
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

        # Record to session history
        try:
            from src.core.memory import SessionHistory
            from src.core.workspace import Workspace

            ws = Workspace.get_instance()
            history = SessionHistory(ws.get_project_root())
            history.log("user", user_text)
            history.log("agent", full_response[:300], model=model_def.name)
        except Exception as e:
            logger.debug(f"Session history write skipped: {e}")

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
        patch_set = self.diff_extractor.extract(full_response, agent_id="orchestrator", model_name=model_name)
        if patch_set.file_count > 0:
            from src.core.workspace import Workspace
            from src.tools.sandbox import E2BSandbox

            sandbox = E2BSandbox()
            should_verify = sandbox.available and healing_attempts < 2 and complexity > 4

            if should_verify:
                ws = Workspace.get_instance()
                verdict = await sandbox.verify_patch(patch_set, ws.get_project_root(), "python")
                has_failures = (
                    verdict.test_result and not verdict.test_result.all_passed and verdict.test_result.failures
                )
                if has_failures:
                    healing_attempts += 1
                    if yield_chunk_callback:
                        await yield_chunk_callback("\n\n[Tests Failed] 🔄 Self-healing retry initiated...\n")
                    first_failure = verdict.test_result.failures[0]
                    failure_msg = first_failure.get("message", str(first_failure))
                    messages.append({"role": "assistant", "content": full_response})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"The test sandbox failed with the following errors upon running your code. "
                                f"Please fix them:\n{failure_msg}\nGenerate the corrected code."
                            ),
                        }
                    )
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
                    f"Executed `{fn_name}` tool ({elapsed:.1f}s)", f"Arguments:\n{args_raw}\n\nResult:\n{result}"
                )

            cmd_msgs.append({"role": "tool", "name": fn_name, "tool_call_id": tc.get("id"), "content": result})
        return cmd_msgs

    def _check_task_budget(self, task_cost: float, usage: dict, model_def) -> None:
        """Check per-task budget limits and emit BudgetExceeded if exceeded."""
        try:
            import textual.app as _tapp  # noqa: I001
            from src.core.events import BudgetExceeded

            current_app = _tapp.active_app.get()
            config = getattr(current_app, "config", None)
            if not config:
                return

            # Update status bar task cost
            try:
                status_bar = current_app.query_one("#status-bar")
                status_bar.task_cost = task_cost
            except Exception:
                pass

            total_tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)

            max_spend = getattr(config.user, "max_spend_per_task", 2.0)
            if task_cost >= max_spend:
                msg = f"Task budget exceeded: ${task_cost:.3f} >= ${max_spend:.2f}"
                current_app.post_message(
                    BudgetExceeded(
                        limit_type="task_spend",
                        limit_value=max_spend,
                        current_value=task_cost,
                        task_description=model_def.name,
                    )
                )
                logger.warning(msg)
                raise RuntimeError(msg)

            # Check per-task token limit
            max_tokens = getattr(config.user, "max_tokens_per_task", 500_000)
            if total_tokens >= max_tokens:
                msg = f"Task token limit exceeded: {total_tokens} >= {max_tokens}"
                current_app.post_message(
                    BudgetExceeded(
                        limit_type="task_tokens",
                        limit_value=float(max_tokens),
                        current_value=float(total_tokens),
                        task_description=model_def.name,
                    )
                )
                logger.warning(msg)
                raise RuntimeError(msg)

        except RuntimeError:
            # F18: Budget RuntimeError must propagate — do NOT swallow it
            raise
        except Exception as e:
            logger.debug(f"Task budget check skipped: {e}")
