"""
Parallel Agent Dispatcher — runs 2-3 AI agents simultaneously on the same task.

Design:
- Each agent runs in its own asyncio.Task with its own tool loop
- All agents share a single asyncio.Queue for output events
- Events are yielded to the caller as they arrive from any agent
- Agents get independent copies of context (no shared mutable state)
- Tool calls (read-only) are safe in parallel; no disk writes during execution
- Cancellation: if one agent fails catastrophically, others continue

Usage:
    dispatcher = ParallelDispatcher()
    async for event in dispatcher.dispatch(task_str, context, models, tools):
        # event = {"type": "agent_chunk", "agent_id": "agent-a", "text": "..."} etc.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator

from src.agents.base import AgentResponse, BaseAgent
from src.agents.factory import PROVIDER_KEY_MAP, AgentFactory
from src.auth.keychain import KeyChainManager
from src.core.diff_engine import DiffExtractor, PatchSet
from src.core.endpoints import resolve_terminal_proxy_url
from src.core.logger import get_logger
from src.core.model_registry import ModelDefinition, ModelRegistry
from src.tools.tool_registry import execute_tool

logger = get_logger("core.parallel_dispatcher")

MAX_TOOL_ITERATIONS = 10


@dataclass
class AgentSlot:
    """Tracks one agent's execution state within a parallel dispatch."""

    agent_id: str  # "agent-a", "agent-b", "agent-c"
    model: ModelDefinition
    agent: BaseAgent | None = None  # Created during dispatch
    status: str = "pending"  # "pending", "running", "completed", "failed", "cancelled"
    start_time: float = 0.0
    end_time: float | None = None
    response_text: str = ""  # Accumulated full response
    patch_set: PatchSet | None = None  # Extracted after completion
    tool_calls_log: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: str | None = None

    @property
    def duration_ms(self) -> int:
        if self.end_time and self.start_time:
            return int((self.end_time - self.start_time) * 1000)
        return 0


@dataclass
class ParallelDispatch:
    """A group of agents running on the same task simultaneously."""

    dispatch_id: str
    task_str: str
    slots: list[AgentSlot]
    mode: str  # "ensemble", "architect", "battle"
    started_at: float = 0.0
    completed_at: float | None = None

    @property
    def all_complete(self) -> bool:
        return all(s.status in ("completed", "failed", "cancelled") for s in self.slots)

    @property
    def successful_slots(self) -> list[AgentSlot]:
        return [s for s in self.slots if s.status == "completed" and s.patch_set]

    @property
    def total_cost(self) -> float:
        return sum(s.cost_usd for s in self.slots)


class ParallelDispatcher:
    """
    Runs multiple agents on the same task concurrently.

    Each agent runs its own tool loop (glob, grep, read_file) independently.
    Output events are interleaved via a shared asyncio.Queue.
    """

    def __init__(self) -> None:
        self._diff_extractor = DiffExtractor()

    DISPATCH_TIMEOUT_SECONDS = 300.0
    AGENT_TIMEOUT_SECONDS = 120.0
    AGENT_STREAM_TIMEOUT_SECONDS = 45.0

    async def dispatch(
        self,
        task_str: str,
        context_messages: list[dict],
        models: list[ModelDefinition],
        tools: list[dict] | None = None,
        mode: str = "ensemble",
    ) -> AsyncIterator[dict]:
        """
        Dispatch task to multiple models in parallel.

        Args:
            task_str: The user's task description
            context_messages: System prompt + repo map + relevant files + task
            models: List of 2-3 ModelDefinitions to run simultaneously
            tools: Agent tool schemas (glob_files, grep_search, read_file) or None
            mode: "ensemble", "architect", or "battle"

        Yields:
            Event dicts for the UI:
            - {"type": "dispatch_started", "dispatch_id": ..., "agents": [...]}
            - {"type": "agent_chunk", "agent_id": ..., "text": ...}
            - {"type": "agent_tool_call", "agent_id": ..., "tool_name": ..., "args": ...}
            - {"type": "agent_complete", "agent_id": ..., "model_name": ..., "response": ...,
               "patch_set": ..., "cost": ..., "duration_ms": ..., "tokens": {...}}
            - {"type": "agent_error", "agent_id": ..., "error": ...}
            - {"type": "all_complete", "dispatch": ParallelDispatch}

        """
        dispatch_id = f"dispatch-{uuid.uuid4().hex[:8]}"

        # Create agent slots
        # Check auth manager for proxy routing
        auth_manager = None
        try:
            import textual.app as _tapp

            current_app = _tapp.active_app.get()
            if hasattr(current_app, "auth_manager"):
                auth_manager = current_app.auth_manager
        except Exception:
            pass

        global_api_key = None
        global_base_url = None
        use_managed = False

        if auth_manager and auth_manager.use_managed_credits:
            access, _ = KeyChainManager.get_auth_tokens()
            if not access:
                yield {
                    "type": "error",
                    "error": "Authentication token missing for managed credits. Please sign in again.",  # noqa: E501
                }
                return
            global_api_key = access
            global_base_url = resolve_terminal_proxy_url()
            use_managed = True

        # Fetch active mode for proxy routing headers
        current_mode = "standard"
        try:
            import textual.app as _tapp

            current_app = _tapp.active_app.get()
            if hasattr(current_app, "orchestrator"):
                current_mode = current_app.orchestrator.mode_manager.active_mode.value
        except Exception:
            pass

        extra_headers = {"X-GPTCGT-Mode": current_mode}

        slots: list[AgentSlot] = []
        for i, model in enumerate(models):
            agent_id = f"Coder {i + 1}"

            if use_managed:
                api_key = global_api_key
                base_url = global_base_url
            else:
                key_name = PROVIDER_KEY_MAP.get(model.provider.value)
                api_key = KeyChainManager.get_key(key_name) if key_name else None
                base_url = None
                if not api_key:
                    logger.warning(f"No API key for {model.provider.value}, skipping {model.name}")
                    continue

            agent = AgentFactory.create_agent(model, api_key=api_key, base_url=base_url, extra_headers=extra_headers)
            slots.append(AgentSlot(agent_id=agent_id, model=model, agent=agent))

        if len(slots) < 2:
            # Need at least 2 runnable agents for parallel dispatch
            yield {
                "type": "error",
                "error": "Need at least 2 runnable models for parallel mode",
            }
            return

        dispatch = ParallelDispatch(
            dispatch_id=dispatch_id,
            task_str=task_str,
            slots=slots,
            mode=mode,
            started_at=time.time(),
        )

        yield {
            "type": "dispatch_started",
            "dispatch_id": dispatch_id,
            "agents": [
                {
                    "agent_id": s.agent_id,
                    "model_name": s.model.name,
                    "model_id": s.model.id,
                    "emoji": s.model.display_emoji,
                    "color": s.model.display_color,
                }
                for s in slots
            ],
        }

        # Shared queue for interleaving output from all agents
        queue: asyncio.Queue[dict] = asyncio.Queue()

        # Launch all agents as concurrent tasks
        agent_tasks = []
        for slot in slots:
            # IMPORTANT: Each agent gets its OWN COPY of context messages
            # Phase 19: Build a custom system prompt injecting this specific model's memory
            from src.core.system_prompt import SystemPromptBuilder

            custom_sys = SystemPromptBuilder.build(model_name=slot.model.name)

            messages_copy = []
            for i, m in enumerate(context_messages):
                new_m = m.copy()
                if i == 0 and new_m.get("role") == "system":
                    new_m["content"] = custom_sys
                messages_copy.append(new_m)

            task = asyncio.create_task(self._run_single_agent_with_timeout(slot, messages_copy, tools, queue))
            agent_tasks.append(task)

        # Yield events as they arrive from any agent
        completed_count = 0
        while completed_count < len(slots):
            try:
                event = await asyncio.wait_for(queue.get(), timeout=self.DISPATCH_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                logger.error(f"Parallel dispatch timed out after {self.DISPATCH_TIMEOUT_SECONDS}s")
                # Cancel remaining agents
                for task in agent_tasks:
                    task.cancel()
                await asyncio.gather(*agent_tasks, return_exceptions=True)
                yield {"type": "error", "error": "Parallel dispatch timed out"}
                return

            yield event

            if event["type"] in ("agent_complete", "agent_error"):
                completed_count += 1

        # All agents finished
        dispatch.completed_at = time.time()

        yield {"type": "all_complete", "dispatch": dispatch}

    async def _run_single_agent_with_timeout(
        self,
        slot: AgentSlot,
        messages: list[dict],
        tools: list[dict] | None,
        queue: asyncio.Queue,
    ) -> None:
        """Wrap _run_single_agent with a per-agent timeout ceiling."""
        try:
            await asyncio.wait_for(
                self._run_single_agent(slot, messages, tools, queue),
                timeout=self.AGENT_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            slot.status = "failed"
            slot.error = f"Agent timed out after {self._format_timeout(self.AGENT_TIMEOUT_SECONDS)}"
            slot.end_time = time.time()
            logger.warning(f"Agent {slot.agent_id} ({slot.model.name}) timed out")
            await queue.put(
                {
                    "type": "agent_error",
                    "agent_id": slot.agent_id,
                    "model_name": slot.model.name,
                    "error": slot.error,
                }
            )
        except asyncio.CancelledError:
            slot.status = "cancelled"
            slot.end_time = time.time()
            raise

    async def _run_single_agent(
        self,
        slot: AgentSlot,
        messages: list[dict],
        tools: list[dict] | None,
        queue: asyncio.Queue,
    ) -> None:
        """
        Run one agent with its full tool loop. Push events to shared queue.

        This is essentially Phase 3's tool call loop, but wrapped per-agent
        and pushing to a queue instead of yielding directly.
        """
        slot.status = "running"
        slot.start_time = time.time()

        try:
            full_response_parts: list[str] = []
            iteration = 0
            while iteration < MAX_TOOL_ITERATIONS:
                iteration += 1
                content_parts: list[str] = []
                final_chunk: AgentResponse | None = None

                import asyncio

                agen = slot.agent.chat_stream(messages)
                while True:
                    try:
                        chunk = await asyncio.wait_for(anext(agen), timeout=self.AGENT_STREAM_TIMEOUT_SECONDS)
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        error_msg = (
                            "Agent watchdog triggered: No response for "
                            f"{self._format_timeout(self.AGENT_STREAM_TIMEOUT_SECONDS)} from {slot.model.name}"
                        )
                        logger.error(error_msg)
                        slot.status = "failed"
                        slot.error = error_msg
                        slot.end_time = time.time()
                        await queue.put(
                            {
                                "type": "agent_error",
                                "agent_id": slot.agent_id,
                                "model_name": slot.model.name,
                                "error": error_msg,
                            }
                        )
                        return

                    if chunk.error:
                        slot.status = "failed"
                        slot.error = chunk.error
                        slot.end_time = time.time()
                        await queue.put(
                            {
                                "type": "agent_error",
                                "agent_id": slot.agent_id,
                                "model_name": slot.model.name,
                                "error": chunk.error,
                            }
                        )
                        return

                    if chunk.text:
                        content_parts.append(chunk.text)
                        full_response_parts.append(chunk.text)
                        await queue.put(
                            {
                                "type": "agent_chunk",
                                "agent_id": slot.agent_id,
                                "model_name": slot.model.name,
                                "text": chunk.text,
                            }
                        )

                    if not chunk.is_streaming or chunk.finish_reason is not None:
                        final_chunk = chunk
                        if chunk.usage:
                            slot.input_tokens += chunk.usage.get("prompt_tokens", 0)
                            slot.output_tokens += chunk.usage.get("completion_tokens", 0)

                    # Check for tool calls
                    if chunk.tool_calls:
                        tool_results = []
                        for tc in chunk.tool_calls:
                            tool_name = tc.get("function", {}).get("name", "")
                            tool_args = tc.get("function", {}).get("arguments", {})
                            if isinstance(tool_args, str):
                                import json

                                try:
                                    tool_args = json.loads(tool_args)
                                except json.JSONDecodeError:
                                    tool_args = {}

                            await queue.put(
                                {
                                    "type": "agent_tool_call",
                                    "agent_id": slot.agent_id,
                                    "model_name": slot.model.name,
                                    "tool_name": tool_name,
                                    "args": tool_args,
                                }
                            )

                            slot.tool_calls_log.append({"tool": tool_name, "args": tool_args})

                            # Execute the tool
                            try:
                                result = execute_tool(tool_name, tool_args)
                            except Exception as e:
                                result = f"Tool error: {e}"

                            tool_results.append(
                                {
                                    "role": "tool",
                                    "content": str(result),
                                    "tool_call_id": tc.get("id", ""),
                                    "name": tool_name,
                                }
                            )

                        # Append assistant message with ALL tool calls + ALL results
                        assistant_content = "".join(content_parts)
                        messages.append(
                            {
                                "role": "assistant",
                                "content": assistant_content or None,
                                "tool_calls": chunk.tool_calls,
                            }
                        )
                        messages.extend(tool_results)
                        content_parts = []
                        break  # Break to re-enter the stream loop with tool results

                # If final chunk had no tool calls, we're done with this agent
                if final_chunk and not final_chunk.tool_calls:
                    break

                # If no final chunk at all (shouldn't happen), break
                if not final_chunk:
                    break

            # Agent completed — accumulate full response
            full_response = "".join(full_response_parts)
            slot.response_text = full_response
            slot.end_time = time.time()

            # Calculate cost
            registry = ModelRegistry()
            slot.cost_usd = registry.calculate_cost(slot.model.id, slot.input_tokens, slot.output_tokens)

            # Extract patches from response
            slot.patch_set = self._diff_extractor.extract(full_response, slot.agent_id, slot.model.name)
            # Populate PatchSet metadata for downstream ELO + cost tracking
            slot.patch_set.cost_usd = slot.cost_usd
            slot.patch_set.generation_time = slot.duration_ms / 1000.0
            slot.patch_set.model_id = slot.model.id

            slot.status = "completed"

            await queue.put(
                {
                    "type": "agent_complete",
                    "agent_id": slot.agent_id,
                    "model_name": slot.model.name,
                    "model_id": slot.model.id,
                    "response": full_response,
                    "patch_set": slot.patch_set,
                    "cost_usd": slot.cost_usd,
                    "duration_ms": slot.duration_ms,
                    "input_tokens": slot.input_tokens,
                    "output_tokens": slot.output_tokens,
                    "tool_calls_count": len(slot.tool_calls_log),
                }
            )

        except asyncio.CancelledError:
            slot.status = "cancelled"
            slot.end_time = time.time()
            raise
        except Exception as e:
            slot.status = "failed"
            slot.error = str(e)
            slot.end_time = time.time()
            logger.error(f"Agent {slot.agent_id} ({slot.model.name}) failed: {e}")
            await queue.put(
                {
                    "type": "agent_error",
                    "agent_id": slot.agent_id,
                    "model_name": slot.model.name,
                    "error": str(e),
                }
            )

    @staticmethod
    def _format_timeout(timeout_seconds: float) -> str:
        return f"{timeout_seconds:g}s"
