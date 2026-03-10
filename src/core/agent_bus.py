"""
Agent Message Bus — central nervous system for inter-agent communication.

Any agent can send a message to any other agent through this bus.
All messages are logged, visible in the Activity Feed, and available
as context for agent conversations.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from src.core.logger import get_logger

logger = get_logger("core.agent_bus")


@dataclass
class AgentMessage:
    """A message from one agent to another."""

    from_agent: str  # "coder", "tester", "arbiter", "scout", "orchestrator"
    to_agent: str  # target agent or "all" for broadcast
    content: str  # the actual message
    msg_type: str = "info"  # "request", "response", "review", "approval", "question"
    timestamp: float = field(default_factory=time.time)
    iteration: int = 0  # which project iteration this belongs to


class AgentMessageBus:
    """
    Central nervous system for inter-agent communication.

    Any agent can send a message to any other agent through this bus.
    Messages are emitted to the UI as AgentConversation events so
    users can watch agents talk to each other in real-time.

    Usage:
        bus = AgentMessageBus()
        bus.send(AgentMessage("coder", "tester", "Here's my code, please test."))
        bus.send(AgentMessage("tester", "coder", "2 tests failed.", msg_type="review"))

        # Read conversation for context injection
        msgs = bus.get_conversation(iteration=3)
    """

    def __init__(self) -> None:
        self._messages: list[AgentMessage] = []
        self._listeners: dict[str, list[Callable]] = {}
        self._iteration: int = 0

    @property
    def current_iteration(self) -> int:
        return self._iteration

    def start_iteration(self, iteration: int) -> None:
        """Mark the start of a new autonomous iteration."""
        self._iteration = iteration
        logger.info(f"Agent bus: starting iteration {iteration}")

    def send(self, msg: AgentMessage) -> None:
        """
        Post a message from one agent to another.  # noqa: D213

        - Appends to the message log
        - Emits AgentConversation event to the UI
        - Wakes any registered listeners for the target agent
        """
        if msg.iteration == 0:
            msg.iteration = self._iteration

        self._messages.append(msg)
        logger.debug(f"[Bus] {msg.from_agent} → {msg.to_agent}: {msg.content[:80]}")

        # Emit to Textual UI
        self._emit_to_ui(msg)

        # Wake listeners
        for listener in self._listeners.get(msg.to_agent, []):
            try:
                listener(msg)
            except Exception as e:
                logger.warning(f"Listener error for {msg.to_agent}: {e}")

        # Broadcast listeners
        if msg.to_agent != "all":
            for listener in self._listeners.get("all", []):
                try:
                    listener(msg)
                except Exception as e:
                    logger.warning(f"Broadcast listener error: {e}")

    def register_listener(self, agent_id: str, callback: Callable) -> None:
        """Register a callback for when a message is sent to an agent."""
        if agent_id not in self._listeners:
            self._listeners[agent_id] = []
        self._listeners[agent_id].append(callback)

    def get_conversation(self, iteration: int | None = None) -> list[AgentMessage]:
        """Full transcript for a given iteration (for agent context windows)."""
        if iteration is None:
            iteration = self._iteration
        return [m for m in self._messages if m.iteration == iteration]

    def get_messages_for(self, agent: str, iteration: int | None = None) -> list[AgentMessage]:
        """Get messages addressed to a specific agent in an iteration."""
        if iteration is None:
            iteration = self._iteration
        return [m for m in self._messages if m.iteration == iteration and m.to_agent in (agent, "all")]

    def get_full_log(self) -> list[AgentMessage]:
        """Get the complete message log across all iterations."""
        return list(self._messages)

    def format_conversation_for_context(self, iteration: int | None = None) -> str:
        """Format the conversation log as text suitable for injection into an agent's context."""
        msgs = self.get_conversation(iteration)
        if not msgs:
            return ""

        lines = ["## Agent Conversation Log"]
        for m in msgs:
            lines.append(f"[{m.from_agent} → {m.to_agent}] ({m.msg_type}): {m.content}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all messages (e.g., at start of new project)."""
        self._messages.clear()
        self._iteration = 0

    @staticmethod
    def _emit_to_ui(msg: AgentMessage) -> None:
        """Post an AgentConversation event to the Textual app."""
        try:
            import textual.app as _tapp  # noqa: I001
            from src.core.events import AgentConversation

            app = _tapp.active_app.get()
            app.post_message(
                AgentConversation(
                    from_agent=msg.from_agent,
                    to_agent=msg.to_agent,
                    content=msg.content,
                    msg_type=msg.msg_type,
                    iteration=msg.iteration,
                )
            )
        except Exception:
            pass  # Silently fail if no UI is running (tests, CLI mode)
