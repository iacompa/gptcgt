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

            target_file = f".gptcgt/agents/{model_name.lower().replace(' ', '_')}.md"
            existing_memory = ""

            if self.workspace.safe_exists(target_file):
                existing_memory = self.workspace.safe_read(target_file)

            # Route exclusively to the cheapest model to protect margins
            available_models = self.registry.get_available_models()
            if not available_models:
                logger.warning("Reflection Engine bypassed: No API keys configured.")
                self._clear_ui_state(model_name)
                return

            # Sort by input token cost to guarantee we only burn fractional cents on this compaction
            cheapest_available = sorted(available_models, key=lambda x: x.input_cost_per_mtok)[0]
            light_model = cheapest_available

            # Prepare the compaction prompt — YAML-structured schema
            system_prompt = (
                "You are an AI Memory Compaction Engine. Your job is to extract a 'lesson learned' "
                "from a failed or overridden AI interaction, and merge it into a persistent memory file.\n\n"
                "OUTPUT FORMAT (STRICT):\n"
                "```\n"
                "---\n"
                "agent: {agent_name}\n"
                "last_updated: {ISO timestamp}\n"
                "version: {increment from existing}\n"
                "total_lessons: {count}\n"
                "---\n"
                "## Routing Patterns\n"
                "- [confidence:high] When X, use Y model\n"
                "## Known Gotchas\n"
                "- [confidence:medium] This project uses ruff not pylint\n"
                "## File Affinity\n"
                "- [scope:project] src/core/config.py is always relevant for settings\n"
                "## Failure Patterns\n"
                "- [timestamp:{ISO}] Description of what went wrong\n"
                "```\n\n"
                "RULES:\n"
                "1. If there is existing memory, merge the new lesson into the correct section.\n"
                "2. Deduplicate — do not repeat facts already present.\n"
                "3. Each bullet MUST have a [confidence:high|medium|low] or [scope:project|file] tag.\n"
                "4. Keep total response UNDER 800 words.\n"
                "5. Preserve the YAML frontmatter. Increment version. Update last_updated and total_lessons."
            )

            from datetime import datetime
            _default_mem = (
                "---\nagent: " + model_name
                + "\nlast_updated: " + datetime.now().isoformat()
                + "\nversion: 0\ntotal_lessons: 0\n---\n"
            )
            _memory_block = existing_memory or _default_mem
            user_prompt = f"""
EXISTING MEMORY:
{_memory_block}

---
FRICTION EVENT ({trigger_event}):
Prompt: {original_prompt}
Output: {agent_output[:1000]}... (truncated)
Failure/Override Reason: {failure_reason}

TASK: Merge the new lesson into the EXISTING MEMORY using the structured schema above. Output only the full updated markdown file.
"""

            # Initialize the base agent for the LIGHT model
            from src.agents.factory import PROVIDER_KEY_MAP, AgentFactory
            from src.auth.keychain import KeyChainManager

            key_name = PROVIDER_KEY_MAP.get(light_model.provider.value)
            api_key = KeyChainManager.get_key(key_name) if key_name else None

            if not api_key:
                logger.warning(
                    f"Reflection Engine skipped: No API key for LIGHT model {light_model.name}"
                )
                self._clear_ui_state(model_name)
                return

            agent = AgentFactory.create_agent(light_model, api_key=api_key)
            agent.config.max_tokens = 800

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            import asyncio

            # Using asyncio.run to execute the async chat_stream within the synchronous thread worker.
            async def _run_stream() -> str:
                full_compacted_memory = ""
                async for chunk in agent.chat_stream(messages):
                    if chunk.text:
                        full_compacted_memory += chunk.text
                return full_compacted_memory

            new_memory = asyncio.run(_run_stream())

            if new_memory:
                self.workspace.safe_write(target_file, new_memory.strip())
                logger.info(f"Successfully compacted memory for {model_name}.")

                # Emit ReflectionRetryHint so the TUI can surface the lesson and
                # inject it into the next dispatch as a system context hint.
                try:
                    from src.core.events import ReflectionRetryHint
                    self.app.call_from_thread(
                        self.app.post_message,
                        ReflectionRetryHint(
                            model_name=model_name,
                            lesson=new_memory.strip()[:600],  # Cap at 600 chars for UI readability
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
            from datetime import datetime
            target_file = f".gptcgt/agents/{model_name.lower().replace(' ', '_')}.md"
            existing = ""
            if self.workspace.safe_exists(target_file):
                existing = self.workspace.safe_read(target_file)

            hit_rate = (relevant_files_used / relevant_files_injected * 100) if relevant_files_injected > 0 else 0

            log_entry = (
                f"\n- [timestamp:{datetime.now().isoformat()}] SUCCESS: "
                f"model={model_id}, tier={tier}, cost=${cost_usd:.4f}, "
                f"tokens={input_tokens}→{output_tokens}, "
                f"file_relevance_hit_rate={hit_rate:.0f}%"
            )

            # Append to existing, cap file at 5000 chars
            new_memory = (existing + log_entry)[-5000:]
            self.workspace.safe_write(target_file, new_memory)
            logger.info(f"Proactive learning logged for {model_name}: ${cost_usd:.4f}, {hit_rate:.0f}% relevance")
        except Exception as e:
            logger.debug(f"Proactive learning log failed: {e}")


