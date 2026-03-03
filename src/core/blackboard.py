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
from datetime import datetime, timedelta
from typing import Any, Callable

from src.core.logger import get_logger

logger = get_logger("core.blackboard")


@dataclass
class BlackboardEntry:
    """Single entry on the blackboard."""

    key: str
    value: Any
    author: str  # agent_id that wrote it
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0  # 0.0-1.0
    ttl_seconds: int = 0  # 0 means lives forever (until task cycle clears)

    @property
    def is_expired(self) -> bool:
        if self.ttl_seconds <= 0:
            return False
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl_seconds)


class AgentBlackboard:
    """
    Thread-safe shared state for multi-agent coordination within a single task.
    Implements a Pub/Sub event bus with TTL expiration.
    """

    _instance: AgentBlackboard | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._entries: dict[str, BlackboardEntry] = {}
        self._history: list[BlackboardEntry] = []
        self._subscribers: dict[str, list[Callable[[BlackboardEntry], None]]] = {}

    @classmethod
    def get_instance(cls) -> AgentBlackboard:
        """Singleton access — one blackboard per app lifecycle."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def subscribe(self, topic: str, callback: Callable[[BlackboardEntry], None]) -> None:
        """Subscribe a callback to a blackboard key (or '*' for all)."""
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(callback)

    def write(self, key: str, value: Any, author: str, confidence: float = 1.0, ttl_seconds: int = 0) -> None:
        """Write a key, triggering pub/sub subscribers."""
        entry = BlackboardEntry(
            key=key, value=value, author=author, confidence=confidence, ttl_seconds=ttl_seconds
        )

        subs = []
        with self._lock:
            self._entries[key] = entry
            self._history.append(entry)
            subs = list(self._subscribers.get(key, [])) + list(self._subscribers.get("*", []))

        logger.debug(f"Blackboard: {author} wrote '{key}' (confidence={confidence:.2f}, ttl={ttl_seconds}s)")

        # Dispatch callbacks asynchronously or outside lock to prevent deadlocks
        for cb in subs:
            try:
                cb(entry)
            except Exception as e:
                logger.error(f"Blackboard pub/sub callback failed for '{key}': {e}")

    def read(self, key: str) -> Any | None:
        """Read a value by key. Returns None if not found or expired."""
        with self._lock:
            entry = self._entries.get(key)
            if entry and entry.is_expired:
                del self._entries[key]
                return None
            return entry.value if entry else None

    def read_entry(self, key: str) -> BlackboardEntry | None:
        """Read the full entry, respecting TTL."""
        with self._lock:
            entry = self._entries.get(key)
            if entry and entry.is_expired:
                del self._entries[key]
                return None
            return entry

    def read_all(self) -> dict[str, BlackboardEntry]:
        """Read all current unexpired entries."""
        with self._lock:
            now = datetime.now()  # noqa: F841
            # Clean expired first
            expired = [k for k, e in self._entries.items() if e.is_expired]
            for k in expired:
                del self._entries[k]
            return dict(self._entries)

    def read_by_author(self, author: str) -> list[BlackboardEntry]:
        """Read all unexpired entries written by a specific agent."""
        all_entries = self.read_all()
        return [e for e in all_entries.values() if e.author == author]

    def clear(self) -> None:
        """Reset blackboard for next task cycle."""
        with self._lock:
            self._entries.clear()
            self._history.clear()
            self._subscribers.clear()
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
