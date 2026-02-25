from __future__ import annotations

import json
from pathlib import Path


def init_gptcgt_workspace(project_root: Path) -> None:
    """Initialize the .gptcgt directory structure for a project."""
    gptcgt_dir = project_root / ".gptcgt"
    gptcgt_dir.mkdir(exist_ok=True)

    (gptcgt_dir / "agents").mkdir(exist_ok=True)
    # NEW: create sessions directory
    (gptcgt_dir / "sessions").mkdir(exist_ok=True)

    # Touch placeholder files
    for f in ["project.md", "routing.json", "history.md", "config.toml", "repo-map.json"]:
        (gptcgt_dir / f).touch(exist_ok=True)

    for f in ["claude.md", "gemini.md", "gpt.md"]:
        (gptcgt_dir / "agents" / f).touch(exist_ok=True)


class ProjectMemory:
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
