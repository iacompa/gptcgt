"""
Phase 3 — Autonomy Blast-Radius Controls.

One central guardrail evaluator that prevents large or unsafe autonomous changes.

Enforces:
  - Hard caps: max files changed, max lines changed, max sensitive files.
  - Protected path classes: billing, auth, migrations, secrets → require approval.
  - Pre-apply risk preview: shows what will change and what policies are hit.
  - Fail-closed: if limits are exceeded, the change is blocked.

No per-agent custom logic. One evaluator used everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.core.logger import get_logger

logger = get_logger("core.guardrails")


# ── Protected path classes ──────────────────────────────────────────────
DEFAULT_PROTECTED_PATHS: dict[str, list[str]] = {
    "billing": ["billing/", "stripe", "payment", "credits"],
    "auth": ["auth/", "middleware/auth", "keychain", "jwt"],
    "migrations": ["migrations/", ".sql"],
    "secrets": [".env", "secrets", "private_key", "api_key"],
}


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


# ── Blast-radius policy ────────────────────────────────────────────────
@dataclass
class BlastRadiusPolicy:
    """Configurable caps for autonomous change scope."""

    max_files: int = 15
    max_lines_changed: int = 500
    max_sensitive_files: int = 2
    protected_paths: dict[str, list[str]] = field(default_factory=lambda: dict(DEFAULT_PROTECTED_PATHS))
    require_approval_for_protected: bool = True


# ── Change summary ──────────────────────────────────────────────────────
@dataclass
class ChangeSummary:
    """Summary of a proposed change set for risk evaluation."""

    files_changed: list[str] = field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0
    sensitive_files: list[str] = field(default_factory=list)
    sensitive_categories: list[str] = field(default_factory=list)


# ── Risk preview ────────────────────────────────────────────────────────
@dataclass
class RiskPreview:
    """Pre-apply risk analysis result."""

    risk_level: RiskLevel = RiskLevel.LOW
    allowed: bool = True
    summary: str = ""
    violations: list[str] = field(default_factory=list)
    change_summary: ChangeSummary = field(default_factory=ChangeSummary)
    requires_approval: bool = False

    def to_text(self) -> str:
        lines = [f"Risk Preview [{self.risk_level.value.upper()}]"]
        cs = self.change_summary
        lines.append(f"  Files: {len(cs.files_changed)}, Lines: +{cs.lines_added}/-{cs.lines_removed}")
        if cs.sensitive_files:
            lines.append(f"  ⚠️  Sensitive: {', '.join(cs.sensitive_files)}")
        if self.violations:
            lines.append("\n  Policy violations:")
            for v in self.violations:
                lines.append(f"    ❌ {v}")
        if self.requires_approval:
            lines.append("\n  🔒 Requires explicit approval for protected paths.")
        return "\n".join(lines)


# ── Central guardrail evaluator ─────────────────────────────────────────
class GuardrailEvaluator:
    """
    Single point of enforcement for blast-radius controls.
    Used by both the autonomous runner and Hub PR creation.
    """

    def __init__(self, policy: BlastRadiusPolicy | None = None) -> None:
        self.policy = policy or BlastRadiusPolicy()

    def evaluate(self, files_changed: list[str], lines_added: int = 0, lines_removed: int = 0) -> RiskPreview:
        """
        Evaluate a proposed change set against the blast-radius policy.
        Returns a RiskPreview with verdict and violations.
        """
        preview = RiskPreview()
        cs = ChangeSummary(
            files_changed=files_changed,
            lines_added=lines_added,
            lines_removed=lines_removed,
        )

        # Classify sensitive files
        for f in files_changed:
            f_lower = f.lower().replace("\\", "/")
            for category, patterns in self.policy.protected_paths.items():
                if any(p in f_lower for p in patterns):
                    cs.sensitive_files.append(f)
                    if category not in cs.sensitive_categories:
                        cs.sensitive_categories.append(category)
                    break

        preview.change_summary = cs
        violations = []

        # Check max files
        if len(files_changed) > self.policy.max_files:
            violations.append(
                f"Files changed ({len(files_changed)}) exceeds limit ({self.policy.max_files})"
            )

        # Check max lines
        total_lines = lines_added + lines_removed
        if total_lines > self.policy.max_lines_changed:
            violations.append(
                f"Lines changed ({total_lines}) exceeds limit ({self.policy.max_lines_changed})"
            )

        # Check sensitive files
        if len(cs.sensitive_files) > self.policy.max_sensitive_files:
            violations.append(
                f"Sensitive files touched ({len(cs.sensitive_files)}) exceeds limit ({self.policy.max_sensitive_files})"
            )

        # Protected path approval gate
        if cs.sensitive_files and self.policy.require_approval_for_protected:
            preview.requires_approval = True

        # Compute verdict
        if violations:
            preview.allowed = False
            preview.risk_level = RiskLevel.BLOCKED
            preview.violations = violations
            preview.summary = f"BLOCKED: {len(violations)} policy violation(s). Changes will not be applied."
        elif preview.requires_approval:
            preview.allowed = False
            preview.risk_level = RiskLevel.HIGH
            preview.summary = (
                f"HIGH RISK: {len(cs.sensitive_files)} protected file(s) touched "
                f"({', '.join(cs.sensitive_categories)}). Requires explicit approval."
            )
        elif len(cs.sensitive_files) > 0:
            preview.allowed = True
            preview.risk_level = RiskLevel.MEDIUM
            preview.summary = f"MEDIUM: {len(cs.sensitive_files)} sensitive file(s), within limits."
        else:
            preview.allowed = True
            preview.risk_level = RiskLevel.LOW
            preview.summary = f"LOW: {len(files_changed)} file(s), no sensitive paths."

        return preview

    def evaluate_patch_set(self, patch_set) -> RiskPreview:
        """Convenience: evaluate from a DiffExtractor PatchSet."""
        files = [str(p.file_path) for p in patch_set.patches]
        added = sum(len(h.new_lines) for p in patch_set.patches for h in p.hunks)
        removed = sum(len(h.old_lines) for p in patch_set.patches for h in p.hunks)
        return self.evaluate(files, added, removed)
