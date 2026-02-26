"""
Context Manager.

Ensures that the total tokens sent to the LLM (messages + attachments + tools)
do not exceed the model's `max_context_tokens` limit, leaving ample room for the output generation.

Operates with the ContextCompactor (Phase 1.8) to trim chat history if needed.
"""

from __future__ import annotations

from typing import Optional

from src.agents.factory import AgentFactory
from src.core.logger import get_logger
from src.core.model_registry import ModelDefinition, ModelRegistry

logger = get_logger("core.context_manager")


def _try_post_truncation_event(reason: str, tokens_dropped: int = 0, files: list[str] | None = None) -> None:
    """
    Post a ContextTruncated event to the live TUI app if one is running.

    Safe to call from any context — silently skips if no app is active.
    """
    try:
        import textual.app as _tapp

        from src.core.events import ContextTruncated
        _tapp.active_app.get().post_message(
            ContextTruncated(reason=reason, tokens_dropped=tokens_dropped, files_truncated=files or [])
        )
    except Exception:
        pass  # No live TUI — normal during tests / CLI usage


class ContextManager:
    """Manages the token budget for LLM requests."""

    def __init__(self, model_id: str):
        self.registry = ModelRegistry()
        self.model_def: Optional[ModelDefinition] = self.registry.get(model_id)

        if not self.model_def:
            # Fallback to a safe minimum if model id somehow isn't found
            logger.warning(f"Model ID {model_id} not found in registry during ContextManager init.")
            self.max_tokens = 8192
            self.output_reserve = 2048
            self.agent_counter = None
        else:
            self.max_tokens = self.model_def.max_context_tokens
            # Reserve room for the output response. We default to ensuring at least 15%
            # or the model's max output tokens size remains available
            self.output_reserve = min(self.model_def.max_output_tokens, int(self.max_tokens * 0.15))
            # Just create a dummy agent instance to access its tokenizer
            self.agent_counter = AgentFactory.create_agent(self.model_def)

    def count_tokens(self, text: str) -> int:
        """Count tokens using the specific model's tokenizer."""
        if not self.agent_counter:
            return len(text) // 4  # Poor man's estimation fallback
        return self.agent_counter.count_tokens(text)

    def count_message_tokens(self, messages: list[dict]) -> int:
        """Count tokens within a list of standard Litellm-formatted message dicts."""
        total = 0
        for m in messages:
            total += 4  # overhead per message
            total += self.count_tokens(str(m.get("content", "")))
            total += self.count_tokens(str(m.get("role", "")))
        total += 2  # overhead for completion
        return total

    def prepare_payload(
        self,
        system_prompt: str,
        history_messages: list[dict],
        new_user_message: str,
        attached_files: list[dict] = None,
    ) -> list[dict]:
        """
        Constructs the final message list that strictly adheres to the available token limit.
        Drops oldest history and truncates oldest file contents if needed.

        Args:
            system_prompt: The assembled system prompt.
            history_messages: Previous chat messages (from ChatStore).
            new_user_message: The new text from the user.
            attached_files: List of dicts e.g., {"path": "main.py", "content": "print('hello')"}

        Returns:
            list[dict]: The final messages array ready to be passed to litellm stream.
                        Format guarantees system prompt is [0] if it exists, and the newest
                        user message (with attachments) is at the very end.

        """
        available_budget = self.max_tokens - self.output_reserve

        # 1. Tally non-negotiables: System Prompt + New User Message
        system_tokens = self.count_tokens(system_prompt) if system_prompt else 0
        new_msg_tokens = self.count_tokens(new_user_message)
        non_negotiable_tokens = system_tokens + new_msg_tokens + 10  # margins

        if non_negotiable_tokens >= available_budget:
            # We are fundamentally screwed (prompt/message too big). Truncate the user message.
            logger.error("System prompt + user message exceeds context limit.")
            _try_post_truncation_event(
                reason="Your message is very long and may be truncated by the model.",
                tokens_dropped=non_negotiable_tokens - available_budget,
            )

        remaining_budget = available_budget - non_negotiable_tokens

        # 2. Add Attachments to the new user message
        # Format: "\n\n--- Filed Attached: {path} ---\n{content}"
        MAX_TOKENS_PER_FILE = 2000  # Hard cap per file to prevent single-file context flood
        attachments_text = ""
        truncated_files: list[str] = []
        if attached_files:
            for f in attached_files:
                f_text = f"\n\n--- File Attached: {f['path']} ---\n{f['content']}\n"
                f_tokens = self.count_tokens(f_text)
                # Per-file hard cap
                if f_tokens > MAX_TOKENS_PER_FILE:
                    char_limit = MAX_TOKENS_PER_FILE * 3
                    trunc_msg = f"\n...[TRUNCATED: {f_tokens} tokens exceeded {MAX_TOKENS_PER_FILE} cap]...\n"
                    f_text = f_text[:char_limit] + trunc_msg
                    f_tokens = self.count_tokens(f_text)
                    truncated_files.append(f["path"])
                    logger.info(f"Per-file cap: {f['path']} truncated to {MAX_TOKENS_PER_FILE} tokens")
                if f_tokens <= remaining_budget:
                    attachments_text += f_text
                    remaining_budget -= f_tokens
                else:
                    # Truncate this file to fit the remaining budget safely
                    logger.warning(f"File {f['path']} is too large, truncating to fit context.")
                    truncated_files.append(f["path"])
                    # Rough truncation (chars)
                    char_budget = remaining_budget * 3
                    if char_budget > 100:
                        truncated_text = f_text[:char_budget] + "\n...[TRUNCATED FOR LENGTH]...\n"
                        attachments_text += truncated_text
                        remaining_budget -= self.count_tokens(truncated_text)
                    break  # Stop adding files since we ran out of space

        if truncated_files:
            _try_post_truncation_event(
                reason="File too large for context window — truncated to fit.",
                files_truncated=truncated_files,
            )

        final_user_content = new_user_message + attachments_text

        # 3. Trim History to fit remaining budget
        final_history = []
        messages_dropped = 0
        if history_messages and remaining_budget > 100:
            # Keep most recent messages that fit within budget (newest first priority)
            accumulated_tokens = 0
            for msg in reversed(history_messages):
                msg_tokens = (
                    self.count_tokens(str(msg.get("content", ""))) + 4
                )  # overhead per message
                if accumulated_tokens + msg_tokens > remaining_budget:
                    messages_dropped += 1
                    continue
                final_history.insert(0, msg)
                accumulated_tokens += msg_tokens

        if messages_dropped > 0:
            _try_post_truncation_event(
                reason=f"{messages_dropped} old message(s) removed from context to fit token limit.",
                tokens_dropped=messages_dropped * 200,  # rough estimate
            )

        # 4. Assemble the array
        # Litellm/Agents want:
        # [{"role": "system", "content": ...}, ...history..., {"role": "user", "content": final}]

        payload = []
        if system_prompt:
            payload.append({"role": "system", "content": system_prompt})

        payload.extend(final_history)
        payload.append({"role": "user", "content": final_user_content})

        total_used = self.count_message_tokens(payload)
        logger.debug(f"Prepared LLM payload: {total_used} / {self.max_tokens} tokens (limit).")

        return payload

