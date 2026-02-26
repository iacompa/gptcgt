"""
TaskBrief — Structured handoff protocol between agents.

Instead of passing raw chat history, the Orchestrator creates a TaskBrief
that every downstream agent receives as a structured context object.
This ensures the Coder, Architect, and Tester all understand the task
identically without re-inferring intent from raw text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TaskBrief:
    """Structured task context passed from Orchestrator to all downstream agents."""

    # Core intent
    intent: str = "chat"
    complexity: int = 5
    user_request: str = ""

    # Scout findings
    mentioned_files: list[str] = field(default_factory=list)
    mentioned_symbols: list[str] = field(default_factory=list)
    relevant_files: list[dict] = field(default_factory=list)  # [{path, content}]

    # Routing decision
    selected_model_id: str = ""
    selected_model_name: str = ""
    quality_tier: str = "standard"

    # Memory hints from .gptcgt/agents/*.md
    memory_hints: list[str] = field(default_factory=list)

    # Orchestrator directives
    reflection_hint: str | None = None
    key_constraints: list[str] = field(default_factory=list)

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    delegation_depth: int = 0

    def to_system_context(self) -> str:
        """Convert to a system prompt fragment for injection."""
        self.validate()  # Ensure required fields before injection
        parts = [
            "# Task Brief",
            f"**Intent:** {self.intent} | **Complexity:** {self.complexity}/10",
            f"**Quality Tier:** {self.quality_tier}",
        ]

        if self.mentioned_files:
            parts.append(f"**Key Files:** {', '.join(self.mentioned_files[:10])}")

        if self.mentioned_symbols:
            parts.append(f"**Key Symbols:** {', '.join(self.mentioned_symbols[:10])}")

        if self.memory_hints:
            parts.append("## Lessons from Memory:")
            for hint in self.memory_hints[:5]:
                parts.append(f"  - {hint}")

        if self.reflection_hint:
            parts.append(f"**Previous Failure Lesson:** {self.reflection_hint}")

        if self.key_constraints:
            parts.append("**Constraints:**")
            for c in self.key_constraints:
                parts.append(f"  - {c}")

        return "\n".join(parts)

    def validate(self) -> None:
        """Validate that required fields are populated. Raises ValueError if not."""
        if not self.intent:
            raise ValueError("TaskBrief.intent is required")
        if not self.user_request:
            raise ValueError("TaskBrief.user_request is required")
        if not 1 <= self.complexity <= 10:
            raise ValueError(f"TaskBrief.complexity must be 1-10, got {self.complexity}")
