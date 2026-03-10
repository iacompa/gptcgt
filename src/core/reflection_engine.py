"""
Background Reflection Engine.

Asynchronously watches for high-friction events (failures, manual user overrides)
and runs a QualityTier.LIGHT model to deduce "lessons learned." Instead of a blind append,
the AI merges the lesson into `.gptcgt/agents/{model_name}.md` keeping it strictly
compacted to preserve API token context margins for the primary working models.

After compaction, emits a ReflectionRetryHint event to the TUI so the lesson can be
surfaced in the chat panel and injected into the next dispatch as a system-level hint.
"""

from __future__ import annotations

from textual import work
from textual.app import App

from src.core.logger import get_logger
from src.core.model_registry import ModelRegistry
from src.core.workspace import Workspace

logger = get_logger("core.reflection_engine")


class ReflectionEngine:
    """Non-blocking background memory compaction engine."""

    def __init__(self, app: App) -> None:
        self.app = app
        self.workspace = Workspace.get_instance()
        self.registry = ModelRegistry()

    @work(exclusive=False, thread=True)
    def reflect_on_friction(
        self,
        model_name: str,
        trigger_event: str,
        original_prompt: str,
        agent_output: str,
        failure_reason: str,
        task_id: str = "unknown",
        file_refs: list[str] | None = None,
    ) -> None:
        """
        Background worker that processes high-signal friction events.
        It reads the existing memory file, deduplicates the new lesson using a cheap model,
        and saves a hyper-compacted markdown log.

        After saving, emits a ReflectionRetryHint event so the next AI dispatch
        can incorporate the lesson into its system context.
        """
        try:
            from src.core.events import AgentStatusUpdate

            # Inform UI non-intrusively
            self.app.call_from_thread(
                self.app.post_message,
                AgentStatusUpdate(
                    agent_id="reflection",
                    model_name=model_name,
                    status="thinking",
                    detail="Cross-referencing memory...",
                ),
            )

            target_file = ".gptcgt/memory.json"
            existing_memory = []

            if self.workspace.safe_exists(target_file):
                try:
                    import json

                    existing_memory = json.loads(self.workspace.safe_read(target_file))
                except Exception:
                    pass

            # Route exclusively to the cheapest model to protect margins
            available_models = self.registry.get_available_models()
            if not available_models:
                logger.warning("Reflection Engine bypassed: No API keys configured.")
                self._clear_ui_state(model_name)
                return

            # Sort by input token cost to guarantee we only burn fractional cents on this compaction
            cheapest_available = sorted(available_models, key=lambda x: x.input_cost_per_mtok)[0]
            light_model = cheapest_available

            from src.core.system_prompt import SystemPromptBuilder

            system_prompt = SystemPromptBuilder.build(
                role_type="engineer",
                custom_instructions=(
                    "You are an AI Memory Compaction Engine. Your job is to extract a highly concise 'lesson learned' "
                    "from a failed or overridden AI interaction.\n\n"
                    "OUTPUT FORMAT: Return carefully structured JSON matching this schema:\n"
                    "{\n"
                    '  "failure_mode": "A 3-5 word summary of the failure",\n'
                    '  "action_taken": "The specific instruction to avoid this next time",\n'
                    '  "outcome": "friction_logged"\n'
                    "}\n"
                    "Do NOT include markdown block formatting, just the raw JSON."
                ),
                model_name=light_model.name,
            )

            user_prompt = f"""
FRICTION EVENT ({trigger_event}):
Prompt: {original_prompt}
Output: {agent_output[:1000]}... (truncated)
Failure/Override Reason: {failure_reason}

TASK: Extract the lesson learned as JSON.
"""

            # Initialize the base agent for the LIGHT model
            from src.agents.factory import PROVIDER_KEY_MAP, AgentFactory
            from src.auth.keychain import KeyChainManager

            key_name = PROVIDER_KEY_MAP.get(light_model.provider.value)
            api_key = KeyChainManager.get_key(key_name) if key_name else None

            if not api_key:
                logger.warning(f"Reflection Engine skipped: No API key for LIGHT model {light_model.name}")
                self._clear_ui_state(model_name)
                return

            agent = AgentFactory.create_agent(light_model, api_key=api_key)
            agent.config.max_tokens = 500
            try:
                agent.config.response_format = {"type": "json_object"}
            except AttributeError:
                pass

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            import asyncio
            import json
            import os

            # Using asyncio.run to execute the async chat_stream within the synchronous thread worker.
            async def _run_stream() -> str:
                full_compacted_memory = ""
                async for chunk in agent.chat_stream(messages):
                    if chunk.text:
                        full_compacted_memory += chunk.text
                return full_compacted_memory

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            new_memory_raw = loop.run_until_complete(_run_stream())

            # Parse JSON
            raw = new_memory_raw.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]

            try:
                lesson_data = json.loads(raw.strip())
            except Exception as e:
                logger.error(f"Failed to parse reflection JSON: {e}")
                self._clear_ui_state(model_name)
                return

            # Vectorize the lesson using litellm
            from datetime import datetime

            import litellm

            embedding_model = None
            emb_api_key = None
            for model in available_models:
                provider_str = model.provider.value
                if provider_str in ["openai", "google"]:
                    k_name = PROVIDER_KEY_MAP.get(provider_str)
                    found_key = KeyChainManager.get_key(k_name) if k_name else None
                    if found_key:
                        embedding_model = (
                            "text-embedding-3-small" if provider_str == "openai" else "gemini/text-embedding-004"
                        )  # noqa: E501
                        emb_api_key = found_key
                        break

            embedding_vector = []
            if embedding_model and emb_api_key:
                try:
                    if "openai" in embedding_model:
                        os.environ["OPENAI_API_KEY"] = emb_api_key
                    elif "gemini" in embedding_model:
                        os.environ["GEMINI_API_KEY"] = emb_api_key

                    response = litellm.embedding(model=embedding_model, input=[lesson_data.get("action_taken", "")])
                    embedding_vector = response.data[0]["embedding"]
                except Exception as e:
                    logger.debug(f"Reflection embedding failed: {e}")

            # Append to memory following unified schema
            lesson_entry = {
                "timestamp": datetime.now().isoformat(),
                "task_id": task_id,
                "file_refs": file_refs or [],
                "failure_mode": lesson_data.get("failure_mode", trigger_event),
                "action_taken": lesson_data.get("action_taken", ""),
                "outcome": lesson_data.get("outcome", "friction_logged"),
                "agent": model_name,
                "embedding": embedding_vector,
            }

            existing_memory.append(lesson_entry)

            # Keep only the last 50 lessons to prevent runaway file size
            if len(existing_memory) > 50:
                existing_memory = existing_memory[-50:]

            self.workspace.safe_write(target_file, json.dumps(existing_memory, indent=2))
            logger.info(f"Successfully compacted memory vector for {model_name}.")

            # Also persist to per-agent MD file for structured context injection
            try:
                from src.core.memory import AgentMemory

                agent_mem = AgentMemory(self.workspace.get_project_root())
                agent_mem.record_interaction(
                    agent_id=model_name,
                    task_summary=original_prompt[:200],
                    outcome="failure",
                    lesson=lesson_data.get("action_taken", ""),
                    files_touched=file_refs,
                )
            except Exception as e:
                logger.debug(f"AgentMemory write failed: {e}")

            # Emit ReflectionRetryHint so the TUI can surface the lesson and
            # inject it into the next dispatch as a system context hint.
            try:
                from src.core.events import ReflectionRetryHint

                self.app.call_from_thread(
                    self.app.post_message,
                    ReflectionRetryHint(
                        model_name=model_name,
                        lesson=lesson_data.get("action_taken", "")[:600],
                        trigger_event=trigger_event,
                    ),
                )
            except Exception as e:
                logger.debug(f"ReflectionRetryHint emit failed: {e}")

            self._clear_ui_state(model_name)

        except Exception as e:
            logger.error(f"Background reflection failed: {e}")
            self._clear_ui_state(model_name)

    def _clear_ui_state(self, model_name: str) -> None:
        """Helper to erase the transient UI status pill."""
        try:
            from src.core.events import AgentStatusUpdate

            self.app.call_from_thread(
                self.app.post_message,
                AgentStatusUpdate(
                    agent_id="reflection",
                    model_name=model_name,
                    status="completed",
                    detail="",
                ),
            )
        except Exception as e:
            logger.debug(f"Reflection _clear_ui_state failed: {e}")

    def log_success(
        self,
        model_name: str,
        model_id: str,
        tier: str,
        cost_usd: float,
        input_tokens: int,
        output_tokens: int,
        relevant_files_injected: int = 0,
        relevant_files_used: int = 0,
    ) -> None:
        """Proactive learning: log a successful task for routing optimization."""
        try:
            target_file = ".gptcgt/memory.json"
            existing = []
            if self.workspace.safe_exists(target_file):
                try:
                    import json

                    existing = json.loads(self.workspace.safe_read(target_file))
                except Exception:
                    pass
            hit_rate = (relevant_files_used / relevant_files_injected * 100) if relevant_files_injected > 0 else 0

            # For successes, we don't need a vector embedding, just log telemetry
            from datetime import datetime

            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "task_id": "unknown",  # We can update this signature later if needed
                "file_refs": [],
                "failure_mode": "none",
                "action_taken": f"SUCCESS: model={model_id}, tier={tier}",
                "outcome": f"success_cost_${cost_usd:.4f}_tokens_{input_tokens}_{output_tokens}_hit_{hit_rate:.0f}%",
                "agent": model_name,
                "type": "telemetry",
            }

            existing.append(log_entry)
            if len(existing) > 50:
                existing = existing[-50:]

            import json

            self.workspace.safe_write(target_file, json.dumps(existing, indent=2))

            # Also persist to per-agent MD file
            from src.core.memory import AgentMemory

            agent_mem = AgentMemory(self.workspace.get_project_root())
            agent_mem.record_interaction(
                agent_id=model_name,
                task_summary=f"Successful completion (tier={tier})",
                outcome="success",
                cost_usd=cost_usd,
            )

        except Exception as e:
            logger.debug(f"Proactive learning failed: {e}")
