from __future__ import annotations

from src.core.chat_store import ChatMessage, MessageRole


class ContextCompactor:
    def __init__(self, max_tokens: int = 100_000) -> None:
        """Initialize with the target model's context window budget."""
        self.max_tokens = max_tokens
        self._summary_cache: str = ""
        self._last_summarized_index: int = -1

    def build_context(
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

        # Only consider USER and AGENT messages for the LLM context (ignore orchestrator/system display msgs)  # noqa: E501
        conversational_msgs = [
            m for m in chat_history if m.role in (MessageRole.USER, MessageRole.AGENT)
        ]

        if len(conversational_msgs) > keep_full_count:
            to_summarize = conversational_msgs[:-keep_full_count]
            recent = conversational_msgs[-keep_full_count:]

            # Use cached summary if the messages to summarize haven't changed
            if not self._summary_cache or len(to_summarize) > self._last_summarized_index:
                self._summary_cache = self._summarize_old_messages(to_summarize)
                self._last_summarized_index = len(to_summarize)

            messages.append(
                {"role": "user", "content": f"[Earlier in session summary: {self._summary_cache}]"}
            )
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

    def _summarize_old_messages(self, messages: list[ChatMessage]) -> str:
        """
        Compress older messages into a brief summary paragraph.
        (In a real implementation, this would call a cheap LLM like gpt-4o-mini here).
        For now, we build a naive textual summary.
        """
        if not messages:
            return ""

        summary = f"Session started at {messages[0].timestamp.strftime('%H:%M:%S')}. "
        tasks = [m.content[:50] + "..." for m in messages if m.role == MessageRole.USER]
        if tasks:
            summary += f"User asked about: {', '.join(tasks[:3])}. "
        summary += f"Total earlier exchanges: {len(messages)}."
        return summary

    def _calculate_budget(
        self,
        system_tokens: int,
        file_tokens: int,
        task_tokens: int,
    ) -> int:
        """Calculate how many tokens remain for conversation history."""
        return self.max_tokens - (system_tokens + file_tokens + task_tokens)
