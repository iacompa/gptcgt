"""
Project Memory — persistent, structured knowledge for gptcgt.

Three layers:
1. ProjectMemory   — project-level facts (languages, deps, conventions)
2. AgentMemory     — per-agent lessons learned (what worked, what failed)
3. SessionHistory  — timestamped log of all interactions
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger("core.memory")


def init_gptcgt_workspace(project_root: Path) -> None:
    """Initialize the .gptcgt directory structure for a project."""
    gptcgt_dir = project_root / ".gptcgt"
    gptcgt_dir.mkdir(exist_ok=True)

    (gptcgt_dir / "agents").mkdir(exist_ok=True)
    (gptcgt_dir / "sessions").mkdir(exist_ok=True)
    (gptcgt_dir / "tests").mkdir(exist_ok=True)

    # Core files
    for f in ["project.md", "routing.json", "history.md", "config.toml", "repo-map.json"]:
        (gptcgt_dir / f).touch(exist_ok=True)

    # Agent knowledge files — one per major provider
    for f in ["claude.md", "gemini.md", "gpt.md", "reflections.md"]:
        (gptcgt_dir / "agents" / f).touch(exist_ok=True)


class ProjectMemory:
    """Project-level facts: detected languages, frameworks, conventions."""

    def __init__(self, project_root: Path):
        self.memory_file = project_root / ".gptcgt" / "memory.json"

    def add_fact(self, fact: str) -> None:
        """Add a new inferred fact to long-term memory."""
        facts = self.get_facts()
        if fact not in facts:
            facts.append(fact)
            self._save(facts)

    def get_facts(self) -> list[str]:
        """Fetch all stored project facts."""
        if not self.memory_file.exists():
            return []
        try:
            return json.loads(self.memory_file.read_text())
        except json.JSONDecodeError:
            return []

    def _save(self, facts: list[str]) -> None:
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self.memory_file.write_text(json.dumps(facts, indent=2))


class AgentMemory:
    """
    Per-agent persistent knowledge written to `.gptcgt/agents/{agent}.md`.

    Each agent accumulates lessons learned, preferences, and outcomes
    in its own markdown file. Token-efficient: keeps only the last
    MAX_LESSONS entries and deduplicates on action_taken.
    """

    MAX_LESSONS = 30
    _SEPARATOR = "\n---\n"

    def __init__(self, project_root: Path):
        self.agents_dir = project_root / ".gptcgt" / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)

    def _agent_file(self, agent_id: str) -> Path:
        """Map agent/model name to its memory file."""
        # Normalize: "claude-3.5-sonnet" → "claude", "gpt-4o" → "gpt", etc.
        name = agent_id.lower()
        if "claude" in name or "anthropic" in name:
            return self.agents_dir / "claude.md"
        elif "gpt" in name or "openai" in name or "o1" in name or "o3" in name:
            return self.agents_dir / "gpt.md"
        elif "gemini" in name or "google" in name:
            return self.agents_dir / "gemini.md"
        else:
            # Any other model (deepseek, xai, etc.) → its own file
            safe = name.split("/")[-1].split("-")[0]
            return self.agents_dir / f"{safe}.md"

    def record_interaction(
        self,
        agent_id: str,
        task_summary: str,
        outcome: str,
        lesson: str = "",
        files_touched: list[str] | None = None,
        cost_usd: float = 0.0,
        checklist_item_id: str = "",
    ) -> None:
        """
        Record an interaction outcome for an agent.

        Args:
            agent_id: Model name or ID (e.g. "claude-3.5-sonnet")
            task_summary: Brief description of what was asked
            outcome: "success", "failure", or "partial"
            lesson: What was learned (empty for successes with no lesson)
            files_touched: List of files the agent modified
            cost_usd: Cost in USD for this interaction
            checklist_item_id: Optional execution-state checklist item ID

        """
        md_file = self._agent_file(agent_id)
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Build the entry
        entry_lines = [
            f"### {now} — {outcome.upper()}",
            f"**Task:** {task_summary[:200]}",
        ]
        if checklist_item_id:
            entry_lines.append(f"**Item:** `{checklist_item_id[:12]}`")
        if lesson:
            entry_lines.append(f"**Lesson:** {lesson[:300]}")
        if files_touched:
            entry_lines.append(f"**Files:** {', '.join(files_touched[:5])}")
        if cost_usd > 0:
            entry_lines.append(f"**Cost:** ${cost_usd:.4f}")
        entry_lines.append("")  # blank line after entry

        entry = "\n".join(entry_lines)

        # Read existing content
        existing = ""
        if md_file.exists():
            existing = md_file.read_text(encoding="utf-8")

        # Deduplicate: skip if same lesson already exists
        if lesson and lesson[:100] in existing:
            logger.debug(f"Skipping duplicate lesson for {agent_id}")
            return

        # Parse entries, add new one, enforce limit
        entries = self._parse_entries(existing)
        entries.append(entry)

        # Keep only the last MAX_LESSONS entries
        if len(entries) > self.MAX_LESSONS:
            entries = entries[-self.MAX_LESSONS :]

        # Write header + entries
        header = f"# {agent_id.split('/')[0].title()} Agent Memory\n\n"
        header += f"_Last updated: {now}_\n"
        md_file.write_text(
            header + self._SEPARATOR + self._SEPARATOR.join(entries),
            encoding="utf-8",
        )
        logger.info(f"Recorded {outcome} for {agent_id} → {md_file.name}")

    def get_context(
        self,
        agent_id: str,
        max_tokens: int = 1500,
        checklist_item_id: str = "",
    ) -> str:
        """
        Get recent agent memory formatted for prompt injection.

        Returns a compact string suitable for insertion into a system prompt.
        Prioritizes lessons (failures) over success telemetry.
        If *checklist_item_id* is given, lessons linked to that item are
        boosted to appear first.
        """
        md_file = self._agent_file(agent_id)
        if not md_file.exists():
            return ""

        content = md_file.read_text(encoding="utf-8")
        if not content.strip():
            return ""

        # Extract only lesson entries (failures are more valuable)
        entries = self._parse_entries(content)
        lesson_entries = [e for e in entries if "**Lesson:**" in e]
        recent = lesson_entries[-5:] if lesson_entries else entries[-3:]

        # Boost entries linked to the current checklist item
        if checklist_item_id and recent:
            linked = [e for e in recent if checklist_item_id[:12] in e]
            others = [e for e in recent if checklist_item_id[:12] not in e]
            recent = linked + others

        if not recent:
            return ""

        result = "## Agent Memory (Past Lessons)\n"
        for entry in recent:
            # Compact: strip markdown headers, keep just the content
            lines = [
                line
                for line in entry.strip().split("\n")
                if line.strip() and not line.startswith("#")
            ]
            result += "\n".join(lines) + "\n"

        # Token-budget cap (rough: 1 token ≈ 4 chars)
        max_chars = max_tokens * 4
        if len(result) > max_chars:
            result = result[:max_chars] + "\n...(truncated)"

        return result

    def _parse_entries(self, text: str) -> list[str]:
        """Parse entries from a markdown file by splitting on separators."""
        if not text.strip():
            return []
        parts = text.split(self._SEPARATOR)
        # Skip the header (first part before first ---)
        entries = [p.strip() for p in parts[1:] if p.strip() and "###" in p]
        return entries


class SessionHistory:
    """Append-only timestamped log written to `.gptcgt/history.md`."""

    def __init__(self, project_root: Path):
        self.history_file = project_root / ".gptcgt" / "history.md"

    def log(self, role: str, content: str, model: str = "") -> None:
        """Append a message to the session history."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        model_tag = f" ({model})" if model else ""

        entry = f"**[{now}] {role}{model_tag}:** {content[:500]}\n\n"

        try:
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            logger.debug(f"Failed to write history: {e}")

    def get_recent(self, count: int = 20) -> str:
        """Get the last N entries from history."""
        if not self.history_file.exists():
            return ""
        try:
            lines = self.history_file.read_text(encoding="utf-8").strip().split("\n\n")
            recent = lines[-count:] if len(lines) > count else lines
            return "\n\n".join(recent)
        except Exception:
            return ""

    def clear(self) -> None:
        """Clear the history file (e.g. on new session)."""
        try:
            self.history_file.write_text("# Session History\n\n", encoding="utf-8")
        except Exception:
            pass
