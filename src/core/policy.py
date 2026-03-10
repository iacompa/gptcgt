"""
Phase 5 — Policy-as-Code for Teams.

One policy file (.gptcgt/policy.yml) with minimal schema.
Supports practical keys only:
  - protected_paths
  - required_checks
  - approval_rules
  - blast_radius_caps
  - mode_caps
  - spending_caps

Enforced at: run start, pre-apply, and pre-PR stages.
No custom scripting engine. Schema is small and versioned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.logger import get_logger

logger = get_logger("core.policy")


# ── Policy schema ───────────────────────────────────────────────────────
@dataclass
class PolicyConfig:
    """Parsed, validated team policy. Minimal and practical."""

    version: str = "1"

    # Protected paths: files/dirs that require approval to modify
    protected_paths: list[str] = field(default_factory=lambda: [
        "billing/", "auth/", "migrations/", ".env",
    ])

    # Required checks before PR creation
    required_checks: list[str] = field(default_factory=lambda: [
        "lint", "tests", "security", "migration",
    ])

    # Approval rules
    approval_rules: dict[str, Any] = field(default_factory=lambda: {
        "require_approval_for_protected": True,
        "min_reviewers": 1,
    })

    # Blast-radius caps
    blast_radius: dict[str, int] = field(default_factory=lambda: {
        "max_files": 15,
        "max_lines": 500,
        "max_sensitive_files": 2,
    })

    # Mode caps: restrict which tiers are available
    mode_caps: dict[str, Any] = field(default_factory=lambda: {
        "allowed_tiers": ["lite", "standard", "max"],
        "default_tier": "standard",
    })

    # Spending caps
    spending_caps: dict[str, float] = field(default_factory=lambda: {
        "daily_limit_usd": 10.0,
        "session_limit_usd": 20.0,
        "per_task_limit_usd": 2.0,
    })


# ── Policy validation errors ───────────────────────────────────────────
@dataclass
class PolicyError:
    field: str
    message: str


# ── Policy parser ───────────────────────────────────────────────────────
class PolicyParser:
    """Parse and validate .gptcgt/policy.yml with clear error messages."""

    VALID_CHECKS = {"lint", "tests", "security", "migration"}
    VALID_TIERS = {"lite", "standard", "max"}

    @classmethod
    def load(cls, project_root: Path | None = None) -> tuple[PolicyConfig, list[PolicyError]]:
        """Load policy from .gptcgt/policy.yml. Returns defaults if file is missing."""
        root = project_root or Path.cwd()
        policy_path = root / ".gptcgt" / "policy.yml"

        if not policy_path.exists():
            return PolicyConfig(), []

        try:
            import yaml
        except ImportError:
            # Graceful fallback: try to use a simpler parser
            try:
                return cls._parse_simple(policy_path)
            except Exception:
                return PolicyConfig(), [PolicyError("yaml", "PyYAML not installed and simple parse failed")]

        try:
            with open(policy_path) as f:
                raw = yaml.safe_load(f)
        except Exception as e:
            return PolicyConfig(), [PolicyError("file", f"Failed to parse policy.yml: {e}")]

        if not isinstance(raw, dict):
            return PolicyConfig(), [PolicyError("root", "policy.yml must be a YAML mapping")]

        return cls._validate(raw)

    @classmethod
    def _validate(cls, raw: dict) -> tuple[PolicyConfig, list[PolicyError]]:
        """Validate raw YAML dict into PolicyConfig."""
        errors = []
        config = PolicyConfig()

        config.version = str(raw.get("version", "1"))

        # Protected paths
        if "protected_paths" in raw:
            val = raw["protected_paths"]
            if isinstance(val, list) and all(isinstance(p, str) for p in val):
                config.protected_paths = val
            else:
                errors.append(PolicyError("protected_paths", "Must be a list of strings"))

        # Required checks
        if "required_checks" in raw:
            val = raw["required_checks"]
            if isinstance(val, list):
                invalid = [c for c in val if c not in cls.VALID_CHECKS]
                if invalid:
                    errors.append(PolicyError(
                        "required_checks",
                        f"Invalid checks: {invalid}. Valid: {sorted(cls.VALID_CHECKS)}"
                    ))
                config.required_checks = [c for c in val if c in cls.VALID_CHECKS]
            else:
                errors.append(PolicyError("required_checks", "Must be a list"))

        # Approval rules
        if "approval_rules" in raw:
            val = raw["approval_rules"]
            if isinstance(val, dict):
                config.approval_rules = val
            else:
                errors.append(PolicyError("approval_rules", "Must be a mapping"))

        # Blast radius
        if "blast_radius" in raw:
            val = raw["blast_radius"]
            if isinstance(val, dict):
                for key in ("max_files", "max_lines", "max_sensitive_files"):
                    if key in val:
                        if isinstance(val[key], int) and val[key] > 0:
                            config.blast_radius[key] = val[key]
                        else:
                            errors.append(PolicyError(f"blast_radius.{key}", "Must be a positive integer"))
            else:
                errors.append(PolicyError("blast_radius", "Must be a mapping"))

        # Mode caps
        if "mode_caps" in raw:
            val = raw["mode_caps"]
            if isinstance(val, dict):
                if "allowed_tiers" in val:
                    tiers = val["allowed_tiers"]
                    if isinstance(tiers, list):
                        invalid = [t for t in tiers if t not in cls.VALID_TIERS]
                        if invalid:
                            errors.append(PolicyError(
                                "mode_caps.allowed_tiers",
                                f"Invalid tiers: {invalid}. Valid: {sorted(cls.VALID_TIERS)}"
                            ))
                        config.mode_caps["allowed_tiers"] = [t for t in tiers if t in cls.VALID_TIERS]
                if "default_tier" in val:
                    if val["default_tier"] in cls.VALID_TIERS:
                        config.mode_caps["default_tier"] = val["default_tier"]
                    else:
                        errors.append(PolicyError(
                            "mode_caps.default_tier",
                            f"Invalid tier: {val['default_tier']}. Valid: {sorted(cls.VALID_TIERS)}"
                        ))
            else:
                errors.append(PolicyError("mode_caps", "Must be a mapping"))

        # Spending caps
        if "spending_caps" in raw:
            val = raw["spending_caps"]
            if isinstance(val, dict):
                for key in ("daily_limit_usd", "session_limit_usd", "per_task_limit_usd"):
                    if key in val:
                        if isinstance(val[key], (int, float)) and val[key] > 0:
                            config.spending_caps[key] = float(val[key])
                        else:
                            errors.append(PolicyError(f"spending_caps.{key}", "Must be a positive number"))
            else:
                errors.append(PolicyError("spending_caps", "Must be a mapping"))

        return config, errors

    @classmethod
    def _parse_simple(cls, path: Path) -> tuple[PolicyConfig, list[PolicyError]]:
        """Minimal YAML-like parser when PyYAML is unavailable."""
        # Only supports flat key-value pairs as a best effort
        config = PolicyConfig()
        return config, [PolicyError("yaml", "PyYAML not installed; using defaults")]


# ── Policy enforcer ─────────────────────────────────────────────────────
class PolicyEnforcer:
    """
    Enforces team policy at three stages:
      1. run_start: validate spending caps and mode restrictions
      2. pre_apply: validate blast-radius limits
      3. pre_pr: validate required checks are met

    Returns (allowed, errors) tuples.
    """

    def __init__(self, policy: PolicyConfig | None = None) -> None:
        self.policy = policy or PolicyConfig()

    def check_run_start(self, current_spend: float = 0.0, mode: str = "standard") -> tuple[bool, list[str]]:
        """Gate at run start: check spending and mode caps."""
        errors = []

        # Mode restriction
        allowed_tiers = self.policy.mode_caps.get("allowed_tiers", ["lite", "standard", "max"])
        if mode not in allowed_tiers:
            errors.append(f"Mode '{mode}' is not allowed by team policy. Allowed: {allowed_tiers}")

        # Spending cap
        daily_limit = self.policy.spending_caps.get("daily_limit_usd", 10.0)
        if current_spend >= daily_limit:
            errors.append(f"Daily spending limit (${daily_limit:.2f}) reached (${current_spend:.2f} spent)")

        return len(errors) == 0, errors

    def check_pre_apply(self, files_changed: list[str], lines_changed: int = 0) -> tuple[bool, list[str]]:
        """Gate before applying changes: check blast-radius."""
        errors = []

        max_files = self.policy.blast_radius.get("max_files", 15)
        if len(files_changed) > max_files:
            errors.append(f"Files changed ({len(files_changed)}) exceeds policy limit ({max_files})")

        max_lines = self.policy.blast_radius.get("max_lines", 500)
        if lines_changed > max_lines:
            errors.append(f"Lines changed ({lines_changed}) exceeds policy limit ({max_lines})")

        # Check for protected paths
        touched_protected = []
        for f in files_changed:
            f_lower = f.lower().replace("\\", "/")
            for pp in self.policy.protected_paths:
                if pp.lower() in f_lower:
                    touched_protected.append(f)
                    break

        max_sensitive = self.policy.blast_radius.get("max_sensitive_files", 2)
        if len(touched_protected) > max_sensitive:
            errors.append(
                f"Protected files touched ({len(touched_protected)}) exceeds limit ({max_sensitive}): "
                f"{', '.join(touched_protected[:5])}"
            )

        if touched_protected and self.policy.approval_rules.get("require_approval_for_protected", True):
            errors.append(
                f"Protected path(s) modified ({', '.join(touched_protected[:3])}). "
                "Explicit approval required by team policy."
            )

        return len(errors) == 0, errors

    def check_pre_pr(self, proof_checks_passed: dict[str, bool]) -> tuple[bool, list[str]]:
        """Gate before PR creation: ensure required checks passed."""
        errors = []

        for check in self.policy.required_checks:
            if check not in proof_checks_passed:
                errors.append(f"Required check '{check}' was not executed")
            elif not proof_checks_passed[check]:
                errors.append(f"Required check '{check}' failed")

        return len(errors) == 0, errors
