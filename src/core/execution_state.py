"""
Execution State — production-grade progress tracking for gptcgt.

JSON-first canonical state that
supports structured agent coordination, token-efficient context slicing,
mid-run scope changes, and backward-compatible derived views.

Architecture:
  execution_state.json  ←── single source of truth (machine-readable)
         │
         ├──▶ execution_checklist.md  (human-readable, generated)
         └──▶ phase.md               (backward-compat, generated)
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from src.core.logger import get_logger

logger = get_logger("core.execution_state")


# ── Enums ───────────────────────────────────────────────────────────────

class ItemStatus(str, Enum):
    """Checklist item lifecycle status."""

    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


# Valid transitions: current_status → set of allowed next statuses
VALID_TRANSITIONS: dict[ItemStatus, set[ItemStatus]] = {
    ItemStatus.PENDING: {ItemStatus.READY, ItemStatus.CANCELED},
    ItemStatus.READY: {ItemStatus.IN_PROGRESS, ItemStatus.BLOCKED, ItemStatus.CANCELED},
    ItemStatus.IN_PROGRESS: {ItemStatus.REVIEW, ItemStatus.BLOCKED, ItemStatus.FAILED, ItemStatus.CANCELED},
    ItemStatus.BLOCKED: {ItemStatus.READY, ItemStatus.IN_PROGRESS, ItemStatus.CANCELED},
    ItemStatus.REVIEW: {ItemStatus.COMPLETED, ItemStatus.IN_PROGRESS, ItemStatus.FAILED},
    ItemStatus.COMPLETED: set(),  # Terminal
    ItemStatus.FAILED: {ItemStatus.READY, ItemStatus.IN_PROGRESS, ItemStatus.CANCELED},
    ItemStatus.CANCELED: set(),  # Terminal
}


class ModelTier(str, Enum):
    LIGHT = "light"
    STANDARD = "standard"
    MAX = "max"


class Route(str, Enum):
    SINGLE = "single"
    BATTLE = "battle"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeRequestStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    APPLIED = "applied"


# ── Artifact Exclusion ──────────────────────────────────────────────────

EXCLUDED_DIRS: frozenset[str] = frozenset({
    ".next", "dist", "build", "coverage", "node_modules",
    ".venv", "venv", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", ".git", ".DS_Store",
    ".gptcgt", ".tox", ".eggs", "*.egg-info",
    "htmlcov", ".coverage", ".cache",
})


def is_excluded_path(path: str) -> bool:
    """Check if a path contains any excluded directory component."""
    parts = Path(path).parts
    for part in parts:
        if part in EXCLUDED_DIRS:
            return True
        # Handle wildcard patterns like *.egg-info
        for pattern in EXCLUDED_DIRS:
            if "*" in pattern and part.endswith(pattern.lstrip("*")):
                return True
    return False


# ── Data Classes ────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(title: str, category: str) -> str:
    """Generate a deterministic, stable ID from title + category."""
    raw = f"{category}::{title}".lower().strip()
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


@dataclass
class ChecklistItem:
    """A single checklist item in the execution state."""

    id: str
    title: str
    category: str = "general"
    status: str = "pending"  # ItemStatus value
    owner_agent: str = ""
    model_tier: str = "standard"  # ModelTier value
    route: str = "single"  # Route value
    dependencies: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    risk_level: str = "low"  # RiskLevel value
    token_budget_in: int = 4000
    token_budget_out: int = 4000
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _now_iso()
        if not self.updated_at:
            self.updated_at = self.created_at


@dataclass
class ChangeRequest:
    """A mid-run scope change request."""

    id: str
    title: str
    description: str = ""
    requested_at: str = ""
    status: str = "proposed"  # ChangeRequestStatus value
    impact_analysis: str = ""
    new_item_ids: list[str] = field(default_factory=list)
    affected_item_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.requested_at:
            self.requested_at = _now_iso()


# ── Execution State ─────────────────────────────────────────────────────

class ExecutionState:
    """
    Canonical machine-readable execution state.

    Single source of truth stored at `.gptcgt/execution_state.json`.
    All markdown views (execution_checklist.md, phase.md) are derived from this.
    """

    STATE_FILE = "execution_state.json"

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(".")
        self._gptcgt_dir = self.project_root / ".gptcgt"
        self._state_path = self._gptcgt_dir / self.STATE_FILE

        self.items: dict[str, ChecklistItem] = {}
        self.change_requests: list[ChangeRequest] = []
        self.project_plan_ref: str = ".gptcgt/project_plan.md"
        self.metadata: dict[str, Any] = {
            "version": 1,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }

    # ── Persistence ─────────────────────────────────────────────────────

    def load(self) -> bool:
        """Load state from disk. Returns True if loaded successfully."""
        if not self._state_path.exists():
            return False
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            self._from_dict(data)
            logger.info(f"Loaded execution state: {len(self.items)} items")
            return True
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load execution state: {e}")
            return False

    def save(self) -> None:
        """Save state to disk (deterministic JSON)."""
        self.metadata["updated_at"] = _now_iso()
        self._gptcgt_dir.mkdir(parents=True, exist_ok=True)
        content = json.dumps(self._to_dict(), indent=2, sort_keys=True, ensure_ascii=False)
        self._state_path.write_text(content + "\n", encoding="utf-8")

    def _to_dict(self) -> dict:
        """Serialize to a deterministic dict."""
        return {
            "metadata": self.metadata,
            "project_plan_ref": self.project_plan_ref,
            "items": {
                item_id: asdict(item)
                for item_id, item in sorted(self.items.items())
            },
            "change_requests": [asdict(cr) for cr in self.change_requests],
        }

    def _from_dict(self, data: dict) -> None:
        """Deserialize from a dict."""
        self.metadata = data.get("metadata", self.metadata)
        self.project_plan_ref = data.get("project_plan_ref", self.project_plan_ref)

        self.items = {}
        for item_id, item_data in data.get("items", {}).items():
            self.items[item_id] = ChecklistItem(**item_data)

        self.change_requests = []
        for cr_data in data.get("change_requests", []):
            self.change_requests.append(ChangeRequest(**cr_data))

    # ── Item Management ─────────────────────────────────────────────────

    def add_item(
        self,
        title: str,
        category: str = "general",
        dependencies: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
        owner_agent: str = "",
        model_tier: str = "standard",
        risk_level: str = "low",
    ) -> ChecklistItem:
        """Add a new checklist item. Returns the created item."""
        item_id = _stable_id(title, category)

        # Avoid duplicates by ID
        if item_id in self.items:
            logger.debug(f"Item already exists: {item_id} ({title})")
            return self.items[item_id]

        item = ChecklistItem(
            id=item_id,
            title=title,
            category=category,
            dependencies=dependencies or [],
            acceptance_criteria=acceptance_criteria or [],
            owner_agent=owner_agent,
            model_tier=model_tier,
            risk_level=risk_level,
        )
        self.items[item_id] = item
        return item

    def update_status(self, item_id: str, new_status: str | ItemStatus) -> bool:
        """
        Update an item's status with transition validation.

        Returns True if the transition was valid and applied, False otherwise.
        """
        if item_id not in self.items:
            logger.warning(f"Item not found: {item_id}")
            return False

        item = self.items[item_id]
        current = ItemStatus(item.status)
        target = ItemStatus(new_status) if isinstance(new_status, str) else new_status

        if target not in VALID_TRANSITIONS[current]:
            logger.warning(
                f"Invalid transition for {item_id}: {current.value} → {target.value}. "
                f"Allowed: {[s.value for s in VALID_TRANSITIONS[current]]}"
            )
            return False

        item.status = target.value
        item.updated_at = _now_iso()
        return True

    def get_items_by_status(self, status: str | ItemStatus) -> list[ChecklistItem]:
        """Get all items with a given status."""
        status_val = status.value if isinstance(status, ItemStatus) else status
        return [item for item in self.items.values() if item.status == status_val]

    def get_ready_items(self) -> list[ChecklistItem]:
        """Get items that are ready (all dependencies completed)."""
        completed_ids = {
            item_id for item_id, item in self.items.items()
            if item.status == ItemStatus.COMPLETED.value
        }

        ready = []
        for item in self.items.values():
            if item.status != ItemStatus.PENDING.value:
                continue
            deps_met = all(dep_id in completed_ids for dep_id in item.dependencies)
            if deps_met:
                ready.append(item)
        return ready

    def get_blocked_items(self) -> list[ChecklistItem]:
        """Get items that are blocked."""
        return self.get_items_by_status(ItemStatus.BLOCKED)

    # ── Dependency Ordering ─────────────────────────────────────────────

    def dependency_order(self) -> list[str]:
        """
        Return item IDs in topological order (dependencies first).

        Raises ValueError if a cycle is detected.
        """
        # Build adjacency: item → items that depend on it
        in_degree: dict[str, int] = {item_id: 0 for item_id in self.items}
        dependents: dict[str, list[str]] = {item_id: [] for item_id in self.items}

        for item_id, item in self.items.items():
            for dep_id in item.dependencies:
                if dep_id in self.items:
                    in_degree[item_id] += 1
                    dependents[dep_id].append(item_id)

        # Kahn's algorithm
        queue: deque[str] = deque()
        for item_id, degree in sorted(in_degree.items()):
            if degree == 0:
                queue.append(item_id)

        order: list[str] = []
        while queue:
            current = queue.popleft()
            order.append(current)
            for dep in sorted(dependents[current]):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)

        if len(order) != len(self.items):
            raise ValueError(
                f"Dependency cycle detected: processed {len(order)}/{len(self.items)} items"
            )

        return order

    def has_cycle(self) -> bool:
        """Check if there is a dependency cycle."""
        try:
            self.dependency_order()
            return False
        except ValueError:
            return True

    # ── Migration from Legacy ───────────────────────────────────────────

    def migrate_from_phase_md(self, phase_md_content: str) -> int:
        """
        Parse legacy phase.md content and import tasks as checklist items.

        Returns the number of items imported.
        """
        imported = 0

        # Parse phase headers and tasks
        current_phase = "general"
        for line in phase_md_content.splitlines():
            line = line.strip()

            # Phase header: ### Phase N: Title ...
            phase_match = re.match(r"###\s*Phase\s*\d+:\s*(.+?)(?:\s*[⬚🔄✅🚫👁️])?$", line)
            if phase_match:
                current_phase = phase_match.group(1).strip()
                continue

            # Task checkbox: - [x] Task name or - [ ] Task name
            task_match = re.match(r"-\s*\[(.)\]\s*(.+)", line)
            if task_match:
                is_done = task_match.group(1).lower() == "x"
                title = task_match.group(2).strip()

                item = self.add_item(title=title, category=current_phase)
                if is_done:
                    # Force to completed (skip transition validation for migration)
                    item.status = ItemStatus.COMPLETED.value
                imported += 1

        logger.info(f"Migrated {imported} items from phase.md")
        return imported

    def migrate_from_plan_md(self, plan_md_content: str) -> int:
        """
        Parse project_plan.md checkbox items into checklist items.

        Returns the number of items imported.
        """
        imported = 0
        current_phase = "general"

        for line in plan_md_content.splitlines():
            line = line.strip()

            # Phase header: ## Phase N: Title
            phase_match = re.match(r"##\s*Phase\s*\d+:\s*(.+)", line)
            if phase_match:
                current_phase = phase_match.group(1).strip()
                continue

            # Task: - [ ] / - [x] / - [/] / - [!]
            task_match = re.match(r"-\s*\[(.)\]\s*(.+)", line)
            if task_match:
                marker = task_match.group(1)
                title = task_match.group(2).strip()
                # Remove failure annotation
                title = re.sub(r"\s*\(FAILED\)\s*$", "", title)

                item = self.add_item(title=title, category=current_phase)

                if marker.lower() == "x":
                    item.status = ItemStatus.COMPLETED.value
                elif marker == "/":
                    item.status = ItemStatus.IN_PROGRESS.value
                elif marker == "!":
                    item.status = ItemStatus.FAILED.value
                # else: remains PENDING

                imported += 1

        logger.info(f"Migrated {imported} items from project_plan.md")
        return imported

    # ── Derived Outputs ─────────────────────────────────────────────────

    def to_checklist_md(self) -> str:
        """Generate human-readable execution_checklist.md."""
        lines = ["# Execution Checklist", "> Generated from execution_state.json", ""]

        # Group by category
        categories: dict[str, list[ChecklistItem]] = {}
        for item in self.items.values():
            categories.setdefault(item.category, []).append(item)

        status_icons = {
            "pending": "⬚", "ready": "🔵", "in_progress": "🔄",
            "blocked": "🚫", "review": "👁️", "completed": "✅",
            "failed": "❌", "canceled": "⊘",
        }

        # Summary
        total = len(self.items)
        completed = sum(1 for i in self.items.values() if i.status == "completed")
        in_progress = sum(1 for i in self.items.values() if i.status == "in_progress")
        blocked = sum(1 for i in self.items.values() if i.status == "blocked")
        lines.append(f"**Progress:** {completed}/{total} completed | {in_progress} in progress | {blocked} blocked")
        lines.append("")

        for category in sorted(categories):
            items = sorted(categories[category], key=lambda i: i.id)
            lines.append(f"## {category}")
            for item in items:
                icon = status_icons.get(item.status, "?")
                check = "x" if item.status == "completed" else " "
                lines.append(f"- [{check}] {icon} `{item.id[:8]}` {item.title}")
                if item.dependencies:
                    dep_names = []
                    for dep_id in item.dependencies:
                        dep = self.items.get(dep_id)
                        dep_names.append(dep.title[:30] if dep else dep_id[:8])
                    lines.append(f"  ↳ depends on: {', '.join(dep_names)}")
            lines.append("")

        # Change requests
        if self.change_requests:
            lines.append("## Change Requests")
            for cr in self.change_requests:
                lines.append(f"- **{cr.title}** ({cr.status}) — {cr.description[:80]}")
            lines.append("")

        return "\n".join(lines)

    def to_phase_md(self) -> str:
        """
        Generate backward-compatible phase.md summary.

        This is a compact summary, NOT the full file map.
        Existing `PhaseTracker` callsites can read this.
        """
        lines = ["# Project Phase Map", "> Auto-generated by gptcgt", ""]

        # Group items into phases by category
        categories: dict[str, list[ChecklistItem]] = {}
        for item in self.items.values():
            categories.setdefault(item.category, []).append(item)

        lines.append("## Development Phases")
        for i, category in enumerate(sorted(categories), 1):
            items = categories[category]
            done = all(it.status == "completed" for it in items)
            in_prog = any(it.status == "in_progress" for it in items)

            if done:
                icon = "✅"
            elif in_prog:
                icon = "🔄"
            else:
                icon = "⬚"

            lines.append(f"### Phase {i}: {category} {icon}")
            for item in sorted(items, key=lambda x: x.id):
                check = "x" if item.status == "completed" else " "
                lines.append(f"- [{check}] {item.title}")
            lines.append("")

        return "\n".join(lines)

    # ── Derived Output Writing ──────────────────────────────────────────

    def write_derived_outputs(self) -> None:
        """Write all derived markdown files."""
        self._gptcgt_dir.mkdir(parents=True, exist_ok=True)

        checklist_path = self._gptcgt_dir / "execution_checklist.md"
        checklist_path.write_text(self.to_checklist_md(), encoding="utf-8")

        phase_path = self._gptcgt_dir / "phase.md"
        phase_path.write_text(self.to_phase_md(), encoding="utf-8")


# ── Context Slicer ──────────────────────────────────────────────────────

class ContextSlicer:
    """
    Token-efficient context slicing for different agent roles.

    Each agent gets only the information relevant to its role,
    bounded by per-tier character budgets (1 token ≈ 4 chars).
    """

    # Per-tier character budgets
    TIER_BUDGETS: dict[str, int] = {
        "light": 2000,      # ~500 tokens
        "standard": 6000,   # ~1500 tokens
        "max": 12000,       # ~3000 tokens
    }

    def __init__(self, state: ExecutionState) -> None:
        self.state = state

    def for_orchestrator(self, tier: str = "standard") -> str:
        """Summary + dependency graph + blockers."""
        budget = self.TIER_BUDGETS.get(tier, self.TIER_BUDGETS["standard"])
        lines = ["# Execution Status"]

        total = len(self.state.items)
        completed = sum(1 for i in self.state.items.values() if i.status == "completed")
        in_prog = sum(1 for i in self.state.items.values() if i.status == "in_progress")
        blocked = sum(1 for i in self.state.items.values() if i.status == "blocked")
        failed = sum(1 for i in self.state.items.values() if i.status == "failed")

        lines.append(f"Progress: {completed}/{total} done, {in_prog} active, {blocked} blocked, {failed} failed")

        # Blockers
        blocked_items = self.state.get_blocked_items()
        if blocked_items:
            lines.append("\nBlockers:")
            for item in blocked_items[:5]:
                lines.append(f"- [{item.id[:8]}] {item.title}")

        # Ready queue
        ready = self.state.get_ready_items()
        if ready:
            lines.append("\nReady Queue:")
            for item in ready[:5]:
                lines.append(f"- [{item.id[:8]}] {item.title} (risk={item.risk_level})")

        # In-progress
        active = self.state.get_items_by_status(ItemStatus.IN_PROGRESS)
        if active:
            lines.append("\nActive:")
            for item in active[:5]:
                lines.append(f"- [{item.id[:8]}] {item.title} → {item.owner_agent or 'unassigned'}")

        result = "\n".join(lines)
        return result[:budget]

    def for_coder(self, item_id: str, tier: str = "standard") -> str:
        """Assigned item + dependencies + acceptance criteria."""
        budget = self.TIER_BUDGETS.get(tier, self.TIER_BUDGETS["standard"])

        item = self.state.items.get(item_id)
        if not item:
            return f"# Task {item_id} not found"

        lines = [f"# Task: {item.title}"]
        lines.append(f"ID: {item.id}")
        lines.append(f"Category: {item.category}")
        lines.append(f"Risk: {item.risk_level}")

        if item.acceptance_criteria:
            lines.append("\n## Acceptance Criteria")
            for ac in item.acceptance_criteria:
                lines.append(f"- {ac}")

        if item.dependencies:
            lines.append("\n## Dependencies")
            for dep_id in item.dependencies:
                dep = self.state.items.get(dep_id)
                if dep:
                    lines.append(f"- [{dep.status}] {dep.title}")

        if item.evidence_refs:
            lines.append("\n## Evidence")
            for ref in item.evidence_refs:
                lines.append(f"- {ref}")

        result = "\n".join(lines)
        return result[:budget]

    def for_tester(self, item_id: str, tier: str = "standard") -> str:
        """Acceptance criteria + changed files + failure history."""
        budget = self.TIER_BUDGETS.get(tier, self.TIER_BUDGETS["standard"])

        item = self.state.items.get(item_id)
        if not item:
            return f"# Task {item_id} not found"

        lines = [f"# Test: {item.title}"]

        if item.acceptance_criteria:
            lines.append("\n## Acceptance Criteria")
            for ac in item.acceptance_criteria:
                lines.append(f"- {ac}")

        if item.evidence_refs:
            lines.append("\n## Evidence/Changed Files")
            for ref in item.evidence_refs:
                lines.append(f"- {ref}")

        # Failure history from previous items in same category
        failed = [
            i for i in self.state.items.values()
            if i.status == "failed" and i.category == item.category
        ]
        if failed:
            lines.append("\n## Prior Failures (same category)")
            for fi in failed[:3]:
                lines.append(f"- {fi.title}")

        result = "\n".join(lines)
        return result[:budget]

    def for_arbiter(self, item_ids: list[str], tier: str = "standard") -> str:
        """Competing outputs + evidence + rubric."""
        budget = self.TIER_BUDGETS.get(tier, self.TIER_BUDGETS["standard"])

        lines = ["# Arbiter Review"]
        for item_id in item_ids:
            item = self.state.items.get(item_id)
            if not item:
                continue
            lines.append(f"\n## {item.title} ({item.id[:8]})")
            if item.acceptance_criteria:
                lines.append("Criteria:")
                for ac in item.acceptance_criteria:
                    lines.append(f"  - {ac}")
            if item.evidence_refs:
                lines.append("Evidence:")
                for ref in item.evidence_refs:
                    lines.append(f"  - {ref}")

        result = "\n".join(lines)
        return result[:budget]


# ── Scope Change Engine ─────────────────────────────────────────────────

class ScopeChangeEngine:
    """
    Handle mid-run scope changes without corrupting existing progress.

    Flow:
      1. User submits a change request (new feature, bug fix, etc.)
      2. Engine analyzes impact (dependencies, risks, budget)
      3. New checklist items are inserted with IDs and dependencies
      4. Queue is reprioritized
      5. Completed work is preserved
    """

    def __init__(self, state: ExecutionState) -> None:
        self.state = state

    def submit_change_request(
        self,
        title: str,
        description: str = "",
        new_items: list[dict] | None = None,
    ) -> ChangeRequest:
        """
        Create a change request with impact analysis.

        Args:
            title: Title of the change request
            description: Detailed description
            new_items: List of dicts with keys: title, category, dependencies, acceptance_criteria

        """
        cr_id = _stable_id(title, "change_request")

        # Impact analysis
        active_items = [
            i for i in self.state.items.values()
            if i.status in ("in_progress", "ready", "pending")
        ]
        completed_items = [
            i for i in self.state.items.values()
            if i.status == "completed"
        ]

        impact = (
            f"Active items: {len(active_items)}, "
            f"Completed items: {len(completed_items)} (preserved), "
            f"New items to add: {len(new_items or [])}"
        )

        cr = ChangeRequest(
            id=cr_id,
            title=title,
            description=description,
            impact_analysis=impact,
        )

        # Create new items
        if new_items:
            for item_spec in new_items:
                item = self.state.add_item(
                    title=item_spec.get("title", "Untitled"),
                    category=item_spec.get("category", "scope_change"),
                    dependencies=item_spec.get("dependencies", []),
                    acceptance_criteria=item_spec.get("acceptance_criteria", []),
                    risk_level=item_spec.get("risk_level", "medium"),
                )
                cr.new_item_ids.append(item.id)

        # Identify potentially affected existing items
        for item in active_items:
            if item.category in [ni.get("category", "") for ni in (new_items or [])]:
                cr.affected_item_ids.append(item.id)

        self.state.change_requests.append(cr)
        return cr

    def apply_change_request(self, cr_id: str) -> bool:
        """Accept and apply a change request."""
        cr = next((c for c in self.state.change_requests if c.id == cr_id), None)
        if not cr:
            logger.warning(f"Change request not found: {cr_id}")
            return False

        cr.status = ChangeRequestStatus.APPLIED.value

        # Auto-promote new items from pending to ready if dependencies met
        completed_ids = {
            item_id for item_id, item in self.state.items.items()
            if item.status == "completed"
        }
        for item_id in cr.new_item_ids:
            item = self.state.items.get(item_id)
            if item and item.status == "pending":
                deps_met = all(d in completed_ids for d in item.dependencies)
                if deps_met:
                    item.status = ItemStatus.READY.value
                    item.updated_at = _now_iso()

        return True

    def reprioritize(self) -> list[str]:
        """
        Reprioritize the queue based on dependencies and risk.

        Returns the ordered list of item IDs.
        """
        try:
            order = self.state.dependency_order()
        except ValueError:
            # Cycle detected — fall back to ID order
            order = sorted(self.state.items.keys())

        # Within the topological order, sort by risk (critical first)
        risk_priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        def sort_key(item_id: str) -> tuple[int, int]:
            item = self.state.items[item_id]
            topo_pos = order.index(item_id) if item_id in order else 999
            risk = risk_priority.get(item.risk_level, 3)
            return (topo_pos, risk)

        return sorted(self.state.items.keys(), key=sort_key)
