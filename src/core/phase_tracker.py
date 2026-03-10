"""Project roadmap and AI navigation system using phase.md."""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Assume workspace is passed in; imported for typing if needed
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.workspace import Workspace

from src.core.execution_state import is_excluded_path
from src.core.logger import get_logger

logger = get_logger("core.phase")


class PhaseStatus(Enum):
    NOT_STARTED = "not_started"  # ⬚
    IN_PROGRESS = "in_progress"  # 🔄
    COMPLETED = "completed"  # ✅
    BLOCKED = "blocked"  # 🚫
    NEEDS_REVIEW = "needs_review"  # 👁️

    @classmethod
    def from_icon(cls, icon: str) -> "PhaseStatus":
        mapping = {
            "⬚": cls.NOT_STARTED,
            "🔄": cls.IN_PROGRESS,
            "✅": cls.COMPLETED,
            "🚫": cls.BLOCKED,
            "👁️": cls.NEEDS_REVIEW,
        }
        return mapping.get(icon, cls.NOT_STARTED)

    def to_icon(self) -> str:
        mapping = {
            self.NOT_STARTED: "⬚",
            self.IN_PROGRESS: "🔄",
            self.COMPLETED: "✅",
            self.BLOCKED: "🚫",
            self.NEEDS_REVIEW: "👁️",
        }
        return mapping[self]


@dataclass
class FileEntry:
    """A single file tracked in the phase map."""

    path: str
    purpose: str
    status: str = "unknown"
    lines: int = 0
    last_modified: str = ""
    dependencies: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)


@dataclass
class Phase:
    """A development phase containing multiple tasks."""

    number: int
    title: str
    description: str
    status: PhaseStatus
    tasks: list[dict] = field(default_factory=list)  # [{"name": str, "status": bool, "notes": str}]
    started_at: str | None = None
    completed_at: str | None = None


class PhaseTracker:
    """
    Manages the .gptcgt/phase.md file.

    This is the AI's primary navigation tool, containing file maps and project phases.
    """

    def __init__(self, workspace: "Workspace") -> None:
        """Initialize with Workspace for safe file access."""
        self._workspace = workspace
        self._phases: list[Phase] = []
        self._file_map: dict[str, FileEntry] = {}
        self._changelog: list[dict] = []

        self.phase_file_path = Path(".gptcgt") / "phase.md"

    def ensure_loaded(self) -> None:
        """Load from disk if it exists, otherwise generate initial."""
        try:
            content = self._workspace.safe_read(self.phase_file_path)
            self.parse_markdown(content)
            logger.info("Loaded existing phase.md")
        except Exception as e:
            # File might not exist or be corrupted
            logger.warning(f"phase.md not found or corrupted ({e}); generating initial scan.")
            content = self.generate_initial()
            self._workspace.safe_write(self.phase_file_path, content)

    def generate_initial(self) -> str:
        """
        Scan the project and generate the initial phase.md content.
        Process: Walk, count lines, create entries, group, basic phases.
        """
        # Very simplistic scan for MVP
        self._file_map.clear()

        # We can implement a deep traversal using os.walk within the safe project root
        root = self._workspace.project_root

        for root_path, dirs, files in self._workspace.safe_walk(root):
            for p in files:
                try:
                    rel_path = p.relative_to(root).as_posix()
                except ValueError:
                    continue

                # Exclude artifacts and build dirs
                if is_excluded_path(rel_path):
                    continue

                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    lines = len(content.splitlines())
                except Exception:
                    lines = 0

                mod_time = datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat()

                self._file_map[rel_path] = FileEntry(
                    path=rel_path,
                    purpose="Auto-detected file",
                    status="complete",
                    lines=lines,
                    last_modified=mod_time,
                )

        # Add a default phase
        if not self._phases:
            self._phases = [
                Phase(
                    number=1,
                    title="Foundation",
                    description="Project structure and base features.",
                    status=PhaseStatus.IN_PROGRESS,
                    tasks=[{"name": "Initial Setup", "status": True, "notes": ""}],
                )
            ]

        return self.render_markdown()

    def update_after_task(self, task_title: str, files_changed: list[str], _task_outcome: str) -> None:
        """Update phase.md after a task completes."""
        self.ensure_loaded()

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # update line counts and last mod for changed files
        root = self._workspace.project_root
        for f in files_changed:
            p = root / f
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                lines = len(content.splitlines())
                mod_time = datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat()

                if f in self._file_map:
                    self._file_map[f].lines = lines
                    self._file_map[f].last_modified = mod_time
                else:
                    self.add_file(f, purpose="Auto-created during task", status="complete")
                    self._file_map[f].lines = lines
                    self._file_map[f].last_modified = mod_time
            except Exception:
                pass

        # Append to changelog
        self._changelog.insert(
            0,
            {
                "date": now,
                "change": task_title,
                "files": ", ".join(files_changed[:3]) + ("..." if len(files_changed) > 3 else ""),
                "phase": "Current",
            },
        )
        self._changelog = self._changelog[:10]  # Keep last 10

        self._save()

    def add_file(self, filepath: str, purpose: str, status: str = "complete") -> None:
        """Register a new file in the phase map."""
        if filepath not in self._file_map:
            self._file_map[filepath] = FileEntry(path=filepath, purpose=purpose, status=status)
            self._save()

    def update_file_status(self, filepath: str, status: str) -> None:
        """Update a file's status (complete, partial, stub, missing)."""
        if filepath in self._file_map:
            self._file_map[filepath].status = status
            self._save()

    def mark_phase_complete(self, phase_number: int) -> None:
        """Mark a phase as completed."""
        for p in self._phases:
            if p.number == phase_number:
                p.status = PhaseStatus.COMPLETED
                p.completed_at = datetime.datetime.now().isoformat()
        self._save()

    def _save(self) -> None:
        """Render and save to disk."""
        content = self.render_markdown()
        self._workspace.safe_write(self.phase_file_path, content)

    def get_context_summary(self) -> str:
        """
        Generate a compact summary for the AI context window.
        ~200 tokens instead of the full file.
        """
        self.ensure_loaded()

        lines = []
        lines.append("Project: Unknown (needs parsing logic implementation for true name)")

        # Active phase
        for p in self._phases:
            if p.status == PhaseStatus.IN_PROGRESS:
                lines.append(f"Phase {p.number} (in progress): {p.title}")
                break

        lines.append("Key files for current context:")
        # We don't have task keywords here, so we just list the first 3
        count = 0
        for path, entry in self._file_map.items():
            if count >= 3:
                break
            lines.append(f"- {path} ({entry.lines} lines, {entry.status})")
            count += 1

        if self._changelog:
            last = self._changelog[0]
            lines.append(f"Recent changes: {last['change']} ({last['files']})")

        return "\n".join(lines)

    def get_file_map_for_task(self, task_keywords: list[str]) -> list[FileEntry]:
        """Return the most relevant files given task keywords."""
        self.ensure_loaded()

        # Simple scoring
        scores = {}
        for entry in self._file_map.values():
            score = 0
            search_text = (entry.path + " " + entry.purpose).lower()
            for kw in task_keywords:
                if kw.lower() in search_text:
                    score += 1
            if score > 0:
                scores[entry.path] = score

        # Sort by score desc
        sorted_paths = [p for p, s in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
        return [self._file_map[p] for p in sorted_paths][:10]

    def render_markdown(self) -> str:
        """Render the complete phase.md content as markdown."""
        lines = []
        lines.append("# Project Phase Map")
        lines.append("> Auto-generated by gptcgt")
        lines.append("")

        lines.append("## Project Structure")
        lines.append("| File | Purpose | Status | Lines |")
        lines.append("|------|---------|--------|-------|")

        # Sort by path
        for path in sorted(self._file_map.keys()):
            e = self._file_map[path]
            lines.append(f"| {e.path} | {e.purpose} | {e.status} | {e.lines} |")

        lines.append("")
        lines.append("## Development Phases")

        for p in sorted(self._phases, key=lambda x: x.number):
            icon = p.status.to_icon()
            lines.append(f"### Phase {p.number}: {p.title} {icon}")
            lines.append(p.description)
            lines.append("")
            for t in p.tasks:
                check = "x" if t.get("status") else " "
                lines.append(f"- [{check}] {t.get('name', 'Un-named task')}")
            lines.append("")

        lines.append("## Changelog")
        lines.append("| Date | Change | Files Affected | Phase |")
        lines.append("|------|--------|---------------|-------|")
        for log in self._changelog:
            lines.append(
                f"| {log.get('date', '')} | {log.get('change', '')} | {log.get('files', '')} | {log.get('phase', '')} |"  # noqa: E501
            )

        return "\n".join(lines)

    def parse_markdown(self, content: str) -> None:
        """Parse an existing phase.md file back into data structures."""
        self._file_map.clear()
        self._phases.clear()
        self._changelog.clear()

        lines = content.splitlines()
        current_section = None
        current_phase = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("## Project Structure"):
                current_section = "structure"
                continue
            elif line.startswith("## Development Phases"):
                current_section = "phases"
                continue
            elif line.startswith("## Changelog"):
                current_section = "changelog"
                continue

            if (
                current_section == "structure"
                and line.startswith("|")
                and not line.startswith("| File |")
                and not line.startswith("|------|")
            ):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 5:
                    path = parts[1]
                    purpose = parts[2]
                    status = parts[3]
                    try:
                        line_count = int(parts[4])
                    except ValueError:
                        line_count = 0
                    self._file_map[path] = FileEntry(path=path, purpose=purpose, status=status, lines=line_count)
            elif current_section == "phases":
                if line.startswith("### Phase "):
                    m = re.match(r"### Phase (\d+):\s*(.*?)\s*(⬚|🔄|✅|🚫|👁️)?$", line)
                    if m:
                        num = int(m.group(1))
                        title = m.group(2).strip()
                        icon = m.group(3) if m.group(3) else "⬚"
                        status_val = PhaseStatus.from_icon(icon)
                        current_phase = Phase(number=num, title=title, description="", status=status_val)
                        self._phases.append(current_phase)
                elif line.startswith("- [") and current_phase:
                    m = re.match(r"- \[(.)\]\s*(.*)", line)
                    if m:
                        is_checked = m.group(1).lower() == "x"
                        name = m.group(2).strip()
                        current_phase.tasks.append({"name": name, "status": is_checked, "notes": ""})
                elif current_phase and not line.startswith("###") and not line.startswith("-"):
                    if current_phase.description:
                        current_phase.description += "\n" + line
                    else:
                        current_phase.description = line
            elif (
                current_section == "changelog"
                and line.startswith("|")
                and not line.startswith("| Date |")
                and not line.startswith("|------|")
            ):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 5:
                    self._changelog.append({"date": parts[1], "change": parts[2], "files": parts[3], "phase": parts[4]})
