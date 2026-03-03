"""
TaskBrief — Structured handoff protocol between agents.

Instead of passing raw chat history, the Orchestrator creates a TaskBrief
that every downstream agent receives as a structured context object.
This ensures the Coder, Architect, and Tester all understand the task
identically without re-inferring intent from raw text.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class TaskBrief(BaseModel):
    """Structured task context passed from Orchestrator to all downstream agents."""

    # Core intent
    intent: str = Field(default="chat", min_length=1)
    complexity: int = Field(default=5, ge=1, le=10)
    user_request: str = Field(min_length=1)

    # Scout findings
    mentioned_files: list[str] = Field(default_factory=list)
    mentioned_symbols: list[str] = Field(default_factory=list)
    relevant_files: list[dict] = Field(default_factory=list)  # [{path, content}]

    # Routing decision
    selected_model_id: str = ""
    selected_model_name: str = ""
    quality_tier: str = "standard"

    # Memory hints from .gptcgt/agents/*.md
    memory_hints: list[str] = Field(default_factory=list)

    # Orchestrator directives
    reflection_hint: str | None = None
    key_constraints: list[str] = Field(default_factory=list)

    # Future-proof fields
    parent_task_id: str | None = None
    budget_override: float | None = None
    forbidden_patterns: list[str] = Field(default_factory=list)

    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    delegation_depth: int = 0

    @field_validator("intent")
    def validate_intent(cls, v: str) -> str:
        if not v:
            raise ValueError("TaskBrief.intent is required")
        return v

    def to_system_context(self) -> str:
        """Convert to a system prompt fragment for injection."""
        parts = [
            "# Task Brief",
            f"**Intent:** {self.intent} | **Complexity:** {self.complexity}/10",
            f"**Quality Tier:** {self.quality_tier}",
        ]

        if self.budget_override is not None:
            parts.append(f"**Spend Budget Override:** ${self.budget_override:.2f}")

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

        if self.forbidden_patterns:
            parts.append("**FORBIDDEN:**")
            for fp in self.forbidden_patterns:
                parts.append(f"  - 🚫 {fp}")

        return "\n".join(parts)
