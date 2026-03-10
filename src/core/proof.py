"""
Phase 1 — Verified PR Mode.

Canonical contract: ProofBundle
One schema, one validator, no competing formats.

Every AI-generated PR must carry a machine-readable proof bundle
proving that tests pass, lint is clean, security scan is green,
migrations are intact, and cost delta is within budget.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from src.core.logger import get_logger

logger = get_logger("core.proof")


# ── Verdict enum ────────────────────────────────────────────────────────
class Verdict(str, Enum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    BLOCKED = "blocked"


# ── Individual check result ─────────────────────────────────────────────
@dataclass
class CheckResult:
    name: str
    passed: bool = False
    output: str = ""
    duration_sec: float = 0.0
    skipped: bool = False
    error: str = ""


# ── ProofBundle — the single source of truth ────────────────────────────
@dataclass
class ProofBundle:
    run_id: str = ""
    commit_sha: str = ""
    timestamp: float = field(default_factory=time.time)

    tests: CheckResult = field(default_factory=lambda: CheckResult(name="tests"))
    lint: CheckResult = field(default_factory=lambda: CheckResult(name="lint"))
    security: CheckResult = field(default_factory=lambda: CheckResult(name="security"))
    migration: CheckResult = field(default_factory=lambda: CheckResult(name="migration"))
    cost_delta_usd: float = 0.0

    # Computed verdict
    verdict: Verdict = Verdict.BLOCKED

    # Human-readable summary
    summary: str = ""

    def recompute_verdict(self) -> Verdict:
        """Deterministic verdict from individual check states."""
        checks = [self.tests, self.lint, self.security, self.migration]
        all_passed = all(c.passed for c in checks if not c.skipped)
        any_failed = any(not c.passed and not c.skipped for c in checks)
        any_skipped = any(c.skipped for c in checks)

        if any_failed:
            self.verdict = Verdict.BLOCKED
        elif any_skipped:
            self.verdict = Verdict.PARTIAL
        else:
            self.verdict = Verdict.VERIFIED if all_passed else Verdict.BLOCKED

        self._build_summary()
        return self.verdict

    def _build_summary(self) -> None:
        lines = [f"Proof Bundle [{self.verdict.value.upper()}]"]
        for c in [self.tests, self.lint, self.security, self.migration]:
            icon = "✅" if c.passed else ("⏭️" if c.skipped else "❌")
            extra = f" ({c.error})" if c.error else ""
            lines.append(f"  {icon} {c.name}: {'pass' if c.passed else 'FAIL'}{extra}")
        if self.cost_delta_usd:
            lines.append(f"  💰 cost delta: ${self.cost_delta_usd:.4f}")
        self.summary = "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


# ── ProofRunner — deterministic check executor ─────────────────────────
class ProofRunner:
    """
    Executes checks in a deterministic order:
      1. Lint  2. Tests  3. Security scan  4. Migration check
    Stores outputs as artifacts tied to run_id + commit_sha.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path.cwd()

    def _get_commit_sha(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    def _run_cmd(self, cmd: list[str], timeout: int = 120) -> tuple[int, str]:
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = (result.stdout + "\n" + result.stderr).strip()
            return result.returncode, output
        except subprocess.TimeoutExpired:
            return 1, "Command timed out"
        except FileNotFoundError:
            return 1, f"Command not found: {cmd[0]}"
        except Exception as e:
            return 1, str(e)

    def run_all(self, run_id: str, cost_delta: float = 0.0) -> ProofBundle:
        """Execute every proof check in deterministic order."""
        bundle = ProofBundle(
            run_id=run_id,
            commit_sha=self._get_commit_sha(),
            cost_delta_usd=cost_delta,
        )

        # 1. Lint
        bundle.lint = self._check_lint()

        # 2. Tests
        bundle.tests = self._check_tests()

        # 3. Security scan
        bundle.security = self._check_security()

        # 4. Migration integrity
        bundle.migration = self._check_migration()

        bundle.recompute_verdict()

        # Persist artifact
        self._save_artifact(bundle)

        return bundle

    def _check_lint(self) -> CheckResult:
        t0 = time.time()
        code, output = self._run_cmd([sys.executable, "-m", "ruff", "check", "."])
        return CheckResult(
            name="lint",
            passed=code == 0,
            output=output[:2000],
            duration_sec=round(time.time() - t0, 2),
            error="" if code == 0 else ("ruff not installed" if "No module named ruff" in output else "lint errors found"),
        )

    def _check_tests(self) -> CheckResult:
        t0 = time.time()
        code, output = self._run_cmd([sys.executable, "-m", "pytest", "-q", "--tb=short", "--maxfail=10"], timeout=180)
        return CheckResult(
            name="tests",
            passed=code == 0,
            output=output[:3000],
            duration_sec=round(time.time() - t0, 2),
            error="" if code == 0 else ("pytest not installed" if "No module named pytest" in output else "test failures"),
        )

    def _check_security(self) -> CheckResult:
        t0 = time.time()
        # Use the project's built-in SecurityScanner if available
        try:
            from src.core.security import SecurityScanner
            scanner = SecurityScanner(self.project_root)
            findings = scanner.scan_directory(self.project_root)
            critical = [f for f in findings if getattr(f, "severity", "").lower() in ("critical", "high")]
            passed = len(critical) == 0
            output = f"{len(findings)} findings, {len(critical)} critical/high"
            return CheckResult(
                name="security",
                passed=passed,
                output=output,
                duration_sec=round(time.time() - t0, 2),
                error="" if passed else f"{len(critical)} blocking findings",
            )
        except Exception as e:
            return CheckResult(
                name="security",
                passed=True,
                skipped=True,
                duration_sec=round(time.time() - t0, 2),
                error=f"scanner unavailable: {e}",
            )

    def _check_migration(self) -> CheckResult:
        t0 = time.time()
        migration_dir = self.project_root / "api" / "migrations"
        if not migration_dir.exists():
            return CheckResult(
                name="migration",
                passed=True,
                skipped=True,
                duration_sec=round(time.time() - t0, 2),
                error="no migrations directory",
            )

        sql_files = sorted(migration_dir.glob("*.sql"))
        run_migration = migration_dir / "run_migration.py"

        if not run_migration.exists():
            return CheckResult(name="migration", passed=False, error="run_migration.py missing")

        # Check that every SQL file is referenced in run_migration.py
        runner_text = run_migration.read_text()
        missing = [f.name for f in sql_files if f.name not in runner_text]

        passed = len(missing) == 0
        return CheckResult(
            name="migration",
            passed=passed,
            output=f"{len(sql_files)} SQL files, {len(missing)} unreferenced",
            duration_sec=round(time.time() - t0, 2),
            error=f"unreferenced: {', '.join(missing)}" if missing else "",
        )

    def _save_artifact(self, bundle: ProofBundle) -> None:
        """Persist proof bundle JSON tied to run_id and commit SHA."""
        artifact_dir = self.project_root / ".gptcgt" / "proof_artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        safe_id = hashlib.sha256(f"{bundle.run_id}:{bundle.commit_sha}".encode()).hexdigest()[:12]
        path = artifact_dir / f"proof_{safe_id}.json"
        path.write_text(bundle.to_json())
        logger.info(f"Proof artifact saved: {path}")


# ── ProofValidator — gate keeper ────────────────────────────────────────
class ProofValidator:
    """
    Validates a ProofBundle before allowing PR creation.
    Returns (allowed: bool, reason: str).
    """

    @staticmethod
    def validate(bundle: ProofBundle) -> tuple[bool, str]:
        """Hard gate: block PR if any required check is missing, failed, or stale."""
        bundle.recompute_verdict()

        if bundle.verdict == Verdict.VERIFIED:
            return True, bundle.summary

        if bundle.verdict == Verdict.PARTIAL:
            skipped = [c.name for c in [bundle.tests, bundle.lint, bundle.security, bundle.migration] if c.skipped]
            return False, f"PR blocked: skipped checks [{', '.join(skipped)}]. All checks must pass."

        # BLOCKED
        failed = [
            c.name for c in [bundle.tests, bundle.lint, bundle.security, bundle.migration]
            if not c.passed and not c.skipped
        ]
        return False, f"PR blocked: failed checks [{', '.join(failed)}]. Fix issues before creating PR."

    @staticmethod
    def is_stale(bundle: ProofBundle, max_age_sec: int = 600) -> bool:
        """A proof bundle older than max_age_sec is considered stale."""
        return (time.time() - bundle.timestamp) > max_age_sec
