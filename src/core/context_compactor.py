"""
Context Compactor — builds the messages array for LLM API calls.

Keeps the last 10 conversational exchanges (20 messages) intact and compresses
older history into a dense semantic summary using the cheapest available model.
Falls back to a fast heuristic when no API keys are configured.
"""

from __future__ import annotations

from src.core.chat_store import ChatMessage, MessageRole
from src.core.logger import get_logger

logger = get_logger("core.context_compactor")


class ContextCompactor:
    def __init__(self, max_tokens: int = 100_000) -> None:
        """Initialize with the target model's context window budget."""
        self.max_tokens = max_tokens
        self._summary_cache: str = ""
        self._last_summarized_index: int = -1

    async def build_context(
        self,
        chat_history: list[ChatMessage],
        current_task: str,
        relevant_files: list[dict],
        repo_map: str,
        agent_context: str,
    ) -> list[dict]:
        """
        Build the messages array to send to the LLM API.
        Keeps the last 10 role exchanges (pairs) intact, and summarizes the rest.
        """
        messages = []

        # 1. Always include System context
        sys_content = f"{agent_context}\n\nRepo Map:\n{repo_map}"
        messages.append({"role": "system", "content": sys_content})

        # Compaction logic: Keep last 10 pairs (approx 20 messages)
        keep_full_count = 20

        # Only consider USER and AGENT messages for the LLM context
        conversational_msgs = [m for m in chat_history if m.role in (MessageRole.USER, MessageRole.AGENT)]

        if len(conversational_msgs) > keep_full_count:
            to_summarize = conversational_msgs[:-keep_full_count]
            recent = conversational_msgs[-keep_full_count:]

            # Use cached summary if the messages to summarize haven't changed
            if not self._summary_cache or len(to_summarize) > self._last_summarized_index:
                self._summary_cache = await self._summarize_old_messages(to_summarize)
                self._last_summarized_index = len(to_summarize)

            messages.append({"role": "user", "content": f"[Earlier in session summary: {self._summary_cache}]"})
        else:
            recent = conversational_msgs

        # Add recent conversation history
        for msg in recent:
            role = "assistant" if msg.role == MessageRole.AGENT else "user"
            messages.append({"role": role, "content": msg.content})

        # Add current task and files (if current task is not already the last user message)
        if current_task and not (recent and recent[-1].content == current_task):
            task_content = f"Current Task:\n{current_task}\n\nRelevant Files:\n"
            for f in relevant_files:
                task_content += f"--- {f.get('path', 'unknown')} ---\n{f.get('content', '')}\n"
            messages.append({"role": "user", "content": task_content})

        # Final safety check against budget
        total_estimated = sum(self._estimate_tokens(str(m.get("content", ""))) for m in messages)
        # Aggressively trim older conversational messages from index 2
        while total_estimated > self.max_tokens and len(messages) > 3:
            popped = messages.pop(2)
            total_estimated -= self._estimate_tokens(str(popped.get("content", "")))

        return messages

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate: len(text) / 4."""
        return len(text) // 4

    async def _summarize_old_messages(self, messages: list[ChatMessage]) -> str:
        """
        Compress older messages into a brief semantic summary.

        Strategy:
        1. Try LLM-based summarization using the cheapest available model.
           This produces a dense, high-quality 2-3 sentence summary that
           preserves user intent, file names, key decisions, and open issues.
        2. Fall back to a fast heuristic if no API keys are configured —
           this is the same approach used pre-2026 but still usable offline.
        """
        if not messages:
            return ""

        # ── Try LLM-based semantic compaction ──────────────────────────
        try:
            summary = await self._llm_summarize(messages)
            if summary:
                logger.debug(f"LLM compaction succeeded: {len(messages)} msgs → {len(summary)} chars")
                return summary
        except Exception as e:
            logger.debug(f"LLM summarization unavailable, using heuristic: {e}")

        # ── Heuristic fallback (offline / no keys) ─────────────────────
        return self._heuristic_summarize(messages)

    async def _llm_summarize(self, messages: list[ChatMessage]) -> str:
        """
        Use the cheapest available model to produce a semantic summary.

        Budget: ~200 output tokens, costs < $0.001 per compaction.
        """
        from src.agents.factory import PROVIDER_KEY_MAP, AgentFactory
        from src.auth.keychain import KeyChainManager
        from src.core.model_registry import ModelRegistry

        registry = ModelRegistry()
        available = registry.get_available_models()
        if not available:
            return ""

        # Pick the cheapest model by input cost to minimize overhead
        cheapest = sorted(available, key=lambda m: m.input_cost_per_mtok)[0]

        key_name = PROVIDER_KEY_MAP.get(cheapest.provider.value)
        api_key = KeyChainManager.get_key(key_name) if key_name else None
        if not api_key:
            return ""

        agent = AgentFactory.create_agent(cheapest, api_key=api_key)
        agent.config.max_tokens = 250  # Keep response tight

        # Build a compact transcript of older messages
        transcript_lines = []
        for msg in messages:
            role_tag = "USER" if msg.role == MessageRole.USER else "ASSISTANT"
            # Truncate each message to control input cost
            snippet = msg.content[:300].replace("\n", " ")
            transcript_lines.append(f"[{role_tag}] {snippet}")

        # Cap total transcript to ~3000 chars (≈750 tokens) to stay cheap
        transcript = "\n".join(transcript_lines)
        if len(transcript) > 3000:
            transcript = transcript[:3000] + "\n...(truncated)"

        llm_messages = [
            {
                "role": "system",
                "content": (
                    "You are a conversation summarizer for a coding assistant. "
                    "Produce a DENSE 2-3 sentence summary of the conversation below. "
                    "PRESERVE: user's intent, file/function names mentioned, decisions made, "
                    "and any unresolved issues. Be specific — no filler words."
                ),
            },
            {
                "role": "user",
                "content": f"Conversation to summarize ({len(messages)} messages):\n\n{transcript}",
            },
        ]

        full_response = ""
        async for chunk in agent.chat_stream(llm_messages):
            if chunk.text:
                full_response += chunk.text

        return full_response.strip()

    @staticmethod
    def _heuristic_summarize(messages: list[ChatMessage]) -> str:
        """
        Fast offline fallback: extract key signals without an LLM call.

        Improved over the original 50-char truncation: extracts file paths,
        function names, and user intent keywords for a more useful summary.
        """
        if not messages:
            return ""

        import re

        user_msgs = [m for m in messages if m.role == MessageRole.USER]
        agent_msgs = [m for m in messages if m.role == MessageRole.AGENT]

        # Extract file references from all messages
        all_text = " ".join(m.content for m in messages)
        file_refs = set(re.findall(r"[\w/]+\.(?:py|ts|tsx|js|jsx|rs|go|md|toml|json)", all_text))

        # Extract user intent from first few user messages
        intents = []
        for m in user_msgs[:5]:
            # Take the first sentence or 100 chars, whichever is shorter
            first_line = m.content.split("\n")[0][:100]
            if first_line:
                intents.append(first_line)

        summary = f"Session with {len(messages)} exchanges. "
        if intents:
            summary += f"User requests: {'; '.join(intents[:3])}. "
        if file_refs:
            summary += f"Files discussed: {', '.join(sorted(file_refs)[:8])}. "
        summary += f"({len(user_msgs)} user msgs, {len(agent_msgs)} agent replies)"

        return summary

    def _calculate_budget(
        self,
        system_tokens: int,
        file_tokens: int,
        task_tokens: int,
    ) -> int:
        """Calculate how many tokens remain for conversation history."""
        return self.max_tokens - (system_tokens + file_tokens + task_tokens)
