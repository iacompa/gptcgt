"""
Agent Blackboard — Shared mutable state for inter-agent coordination.

The blackboard is a per-task scratchpad that any agent can read/write.
This enables Architect→Scout→Coder coordination: the Architect writes
the plan, the Scout notes which files it found relevant, and the Coder
reads both before generating code.

The blackboard is ephemeral (lives for one task cycle) and is NOT
persisted to disk — it exists only in memory during a dispatch.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.core.logger import get_logger

logger = get_logger("core.blackboard")


@dataclass
class BlackboardEntry:
    """Single entry on the blackboard."""
    key: str
    value: Any
    author: str  # agent_id that wrote it
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    confidence: float = 1.0  # 0.0-1.0


class AgentBlackboard:
    """
    Thread-safe shared state for multi-agent coordination within a single task.

    Usage:
        bb = AgentBlackboard()
        bb.write("architectural_plan", plan_text, author="architect")
        bb.write("relevant_files", file_list, author="scout")
        plan = bb.read("architectural_plan")
        all_entries = bb.read_all()
    """

    _instance: AgentBlackboard | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._entries: dict[str, BlackboardEntry] = {}
        self._history: list[BlackboardEntry] = []

    @classmethod
    def get_instance(cls) -> AgentBlackboard:
        """Singleton access — one blackboard per app lifecycle."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def write(self, key: str, value: Any, author: str, confidence: float = 1.0) -> None:
        """Write or overwrite a key on the blackboard."""
        entry = BlackboardEntry(
            key=key, value=value, author=author, confidence=confidence
        )
        with self._lock:
            self._entries[key] = entry
            self._history.append(entry)
        logger.debug(f"Blackboard: {author} wrote '{key}' (confidence={confidence:.2f})")

    def read(self, key: str) -> Any | None:
        """Read a value by key. Returns None if not found."""
        with self._lock:
            entry = self._entries.get(key)
            return entry.value if entry else None

    def read_entry(self, key: str) -> BlackboardEntry | None:
        """Read the full entry (including author, timestamp, confidence)."""
        with self._lock:
            return self._entries.get(key)

    def read_all(self) -> dict[str, BlackboardEntry]:
        """Read all current entries."""
        with self._lock:
            return dict(self._entries)

    def read_by_author(self, author: str) -> list[BlackboardEntry]:
        """Read all entries written by a specific agent."""
        with self._lock:
            return [e for e in self._entries.values() if e.author == author]

    def clear(self) -> None:
        """Reset blackboard for next task cycle."""
        with self._lock:
            self._entries.clear()
            self._history.clear()
        logger.debug("Blackboard cleared for new task cycle.")

    def to_context_string(self) -> str:
        """Serialize blackboard to a string for injection into agent context."""
        with self._lock:
            if not self._entries:
                return ""
            parts = ["# Agent Blackboard (Shared State)"]
            for key, entry in self._entries.items():
                val_preview = str(entry.value)[:500]
                parts.append(
                    f"## {key} (by {entry.author}, confidence={entry.confidence:.0%})\n{val_preview}"
                )
            return "\n\n".join(parts)

    @property
    def size(self) -> int:
        return len(self._entries)
