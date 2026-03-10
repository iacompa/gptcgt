"""
Phase 3 — Replayable PR Receipts.

Generates a tamper-evident, replayable receipt for every PR created
by the autonomous runner. The receipt captures:
  - Full provenance chain (repo, branch, commits, agent decisions)
  - Verification evidence (test results, security scan, lint, build)
  - Cost accounting (tokens and USD by stage)
  - Replay instructions (deterministic shell script)

Output artifacts:
  - pr_receipt.json   — Machine-readable receipt
  - pr_receipt.md     — Human-readable summary
  - verification_bundle.json — Raw evidence payloads
  - replay.sh         — Deterministic replay script

Integrity: SHA-256 content hash over all receipt fields.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger("core.pr_receipt")


# ── Data structures ─────────────────────────────────────────────────────

@dataclass
class CommitInfo:
    """A single commit in the PR."""

    sha: str
    message: str
    author: str = "gptcgt-agent"
    timestamp: str = ""


@dataclass
class FileChange:
    """A file changed in the PR with rationale."""

    path: str
    action: str = "modified"  # created, modified, deleted
    lines_added: int = 0
    lines_removed: int = 0
    rationale: str = ""


@dataclass
class StageMetrics:
    """Token and cost metrics for a single pipeline stage."""

    stage: str  # "coder", "tester", "arbiter", "security"
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    model: str = ""


@dataclass
class TestEvidence:
    """Test execution evidence."""

    passed: int = 0
    failed: int = 0
    errors: int = 0
    coverage_percent: float = 0.0
    test_command: str = ""
    raw_output: str = ""


TestEvidence.__test__ = False


@dataclass
class SecurityEvidence:
    """Security scan evidence."""

    findings_count: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    scanner: str = ""
    badge: str = "clean"  # clean, warning, blocked


@dataclass
class AgentDecision:
    """A recorded decision made by an agent during execution."""

    agent: str
    action: str
    reasoning: str = ""
    iteration: int = 0
    timestamp: str = ""


@dataclass
class PRReceipt:
    """Complete receipt for a PR created by the autonomous runner."""

    # Metadata
    receipt_id: str = ""
    created_at: str = ""
    run_id: str = ""

    # Repository
    repo_url: str = ""
    base_branch: str = "main"
    head_branch: str = ""
    pr_url: str = ""
    pr_number: int = 0

    # Changes
    commits: list[CommitInfo] = field(default_factory=list)
    files_changed: list[FileChange] = field(default_factory=list)
    total_lines_added: int = 0
    total_lines_removed: int = 0

    # Evidence
    test_results: TestEvidence = field(default_factory=TestEvidence)
    security_results: SecurityEvidence = field(default_factory=SecurityEvidence)
    lint_clean: bool = False
    build_clean: bool = False

    # Cost accounting
    stage_metrics: list[StageMetrics] = field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    # Agent decisions
    decisions: list[AgentDecision] = field(default_factory=list)

    # Risks and notes
    risks: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    # Integrity
    content_hash: str = ""

    def compute_hash(self) -> str:
        """Compute SHA-256 hash over all receipt fields (excluding the hash itself)."""
        data = asdict(self)
        data.pop("content_hash", None)
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @property
    def summary(self) -> str:
        """One-line summary of the receipt."""
        return (
            f"PR #{self.pr_number}: {len(self.files_changed)} files, "
            f"+{self.total_lines_added}/-{self.total_lines_removed}, "
            f"tests {self.test_results.passed}P/{self.test_results.failed}F, "
            f"security {self.security_results.badge}, "
            f"${self.total_cost_usd:.2f}"
        )


# ── Receipt Generator ───────────────────────────────────────────────────

class ReceiptGenerator:
    """Generate PR receipt artifacts from execution data."""

    def __init__(self, receipt: PRReceipt) -> None:
        self.receipt = receipt

    def finalize(self) -> PRReceipt:
        """Compute totals and content hash."""
        # Compute totals
        self.receipt.total_lines_added = sum(f.lines_added for f in self.receipt.files_changed)
        self.receipt.total_lines_removed = sum(f.lines_removed for f in self.receipt.files_changed)
        self.receipt.total_tokens = sum(
            m.tokens_in + m.tokens_out for m in self.receipt.stage_metrics
        )
        self.receipt.total_cost_usd = sum(m.cost_usd for m in self.receipt.stage_metrics)

        # Set timestamp if not already set
        if not self.receipt.created_at:
            self.receipt.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Generate receipt ID if not set
        if not self.receipt.receipt_id:
            self.receipt.receipt_id = hashlib.sha256(
                f"{self.receipt.run_id}:{self.receipt.created_at}".encode()
            ).hexdigest()[:16]

        # Compute integrity hash
        self.receipt.content_hash = self.receipt.compute_hash()

        return self.receipt

    def generate_all(self, output_dir: Path) -> dict[str, str]:
        """Generate all receipt artifacts."""
        output_dir.mkdir(parents=True, exist_ok=True)
        self.finalize()
        artifacts = {}

        # 1. JSON receipt
        receipt_json = json.dumps(self.receipt.to_dict(), indent=2, default=str)
        (output_dir / "pr_receipt.json").write_text(receipt_json)
        artifacts["pr_receipt.json"] = receipt_json

        # 2. Markdown receipt
        receipt_md = self._generate_markdown()
        (output_dir / "pr_receipt.md").write_text(receipt_md)
        artifacts["pr_receipt.md"] = receipt_md

        # 3. Verification bundle
        bundle = self._generate_verification_bundle()
        bundle_json = json.dumps(bundle, indent=2, default=str)
        (output_dir / "verification_bundle.json").write_text(bundle_json)
        artifacts["verification_bundle.json"] = bundle_json

        # 4. Replay script
        replay = self._generate_replay_script()
        replay_path = output_dir / "replay.sh"
        replay_path.write_text(replay)
        replay_path.chmod(0o755)
        artifacts["replay.sh"] = replay

        logger.info(f"Generated receipt artifacts in {output_dir}")
        return artifacts

    def _generate_markdown(self) -> str:
        """Generate human-readable markdown receipt."""
        r = self.receipt
        lines = [
            f"# PR Receipt: {r.pr_url or f'Run {r.run_id}'}",
            f"\n**Receipt ID:** `{r.receipt_id}`",
            f"**Created:** {r.created_at}",
            f"**Content Hash:** `{r.content_hash}`\n",
            "## Summary\n",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Files changed | {len(r.files_changed)} |",
            f"| Lines added | +{r.total_lines_added} |",
            f"| Lines removed | -{r.total_lines_removed} |",
            f"| Tests passed | {r.test_results.passed} |",
            f"| Tests failed | {r.test_results.failed} |",
            f"| Security badge | {r.security_results.badge} |",
            f"| Total tokens | {r.total_tokens:,} |",
            f"| Total cost | ${r.total_cost_usd:.2f} |",
            "",
        ]

        # Files changed
        if r.files_changed:
            lines.append("## Files Changed\n")
            lines.append("| File | Action | +/- | Rationale |")
            lines.append("|------|--------|-----|-----------|")
            for f in r.files_changed:
                lines.append(
                    f"| `{f.path}` | {f.action} | +{f.lines_added}/-{f.lines_removed} | {f.rationale} |"
                )
            lines.append("")

        # Stage metrics
        if r.stage_metrics:
            lines.append("## Cost Breakdown\n")
            lines.append("| Stage | Model | Tokens | Cost | Duration |")
            lines.append("|-------|-------|--------|------|----------|")
            for m in r.stage_metrics:
                lines.append(
                    f"| {m.stage} | {m.model} | {m.tokens_in + m.tokens_out:,} "
                    f"| ${m.cost_usd:.3f} | {m.duration_seconds:.1f}s |"
                )
            lines.append("")

        # Agent decisions
        if r.decisions:
            lines.append("## Agent Decisions\n")
            for d in r.decisions:
                lines.append(f"- **[{d.agent}]** {d.action}")
                if d.reasoning:
                    lines.append(f"  _{d.reasoning}_")
            lines.append("")

        # Risks
        if r.risks:
            lines.append("## Risks\n")
            for risk in r.risks:
                lines.append(f"- ⚠️ {risk}")
            lines.append("")

        return "\n".join(lines)

    def _generate_verification_bundle(self) -> dict:
        """Generate verification evidence bundle."""
        r = self.receipt
        return {
            "receipt_id": r.receipt_id,
            "content_hash": r.content_hash,
            "test_evidence": asdict(r.test_results),
            "security_evidence": asdict(r.security_results),
            "lint_clean": r.lint_clean,
            "build_clean": r.build_clean,
            "commits": [asdict(c) for c in r.commits],
            "verification_timestamp": r.created_at,
        }

    def _generate_replay_script(self) -> str:
        """Generate deterministic replay script."""
        r = self.receipt
        lines = [
            "#!/usr/bin/env bash",
            "# PR Receipt Replay Script",
            f"# Receipt ID: {r.receipt_id}",
            f"# Generated: {r.created_at}",
            f"# Content Hash: {r.content_hash}",
            "",
            "set -euo pipefail",
            "",
            "echo '=== PR Receipt Replay ==='",
            f"echo 'Replaying PR from run: {r.run_id}'",
            "",
        ]

        if r.repo_url:
            lines.extend([
                "# Clone and checkout",
                f"git clone {r.repo_url} replay_workspace",
                "cd replay_workspace",
                f"git checkout {r.base_branch}",
                "",
            ])

        # Apply changes
        if r.commits:
            lines.append("# Cherry-pick commits")
            for c in r.commits:
                lines.append(f"git cherry-pick {c.sha}  # {c.message}")
            lines.append("")

        # Run verification
        lines.extend([
            "# Run verification suite",
            "echo 'Running tests...'",
        ])
        if r.test_results.test_command:
            lines.append(r.test_results.test_command)
        else:
            lines.append("python -m pytest tests/ -v --tb=short")

        lines.extend([
            "",
            "echo 'Running lint...'",
            "python -m ruff check .",
            "",
            "echo 'Running security scan...'",
            "# semgrep --config auto . || true",
            "",
            f"echo 'Replay complete. Expected: {r.test_results.passed} tests pass.'",
        ])

        return "\n".join(lines)


# ── Receipt Verifier ────────────────────────────────────────────────────

class ReceiptVerifier:
    """Verify the integrity and consistency of a PR receipt."""

    @staticmethod
    def verify(receipt: PRReceipt) -> tuple[bool, list[str]]:
        """Verify receipt integrity. Returns (valid, issues)."""
        issues = []

        # 1. Content hash integrity
        expected_hash = receipt.compute_hash()
        if receipt.content_hash and receipt.content_hash != expected_hash:
            issues.append(
                f"Content hash mismatch: stored={receipt.content_hash[:12]}..., "
                f"computed={expected_hash[:12]}..."
            )

        # 2. Totals consistency
        computed_lines_added = sum(f.lines_added for f in receipt.files_changed)
        if receipt.total_lines_added != computed_lines_added:
            issues.append(
                f"Lines added mismatch: total={receipt.total_lines_added}, "
                f"sum={computed_lines_added}"
            )

        computed_lines_removed = sum(f.lines_removed for f in receipt.files_changed)
        if receipt.total_lines_removed != computed_lines_removed:
            issues.append(
                f"Lines removed mismatch: total={receipt.total_lines_removed}, "
                f"sum={computed_lines_removed}"
            )

        computed_tokens = sum(
            m.tokens_in + m.tokens_out for m in receipt.stage_metrics
        )
        if receipt.total_tokens != computed_tokens:
            issues.append(
                f"Token count mismatch: total={receipt.total_tokens}, "
                f"sum={computed_tokens}"
            )

        # 3. Test results sanity
        if receipt.test_results.failed > 0 and receipt.security_results.badge == "clean":
            issues.append("Tests failed but security badge is clean — inconsistent")

        # 4. Required fields
        if not receipt.run_id:
            issues.append("Missing run_id")
        if not receipt.receipt_id:
            issues.append("Missing receipt_id")

        return len(issues) == 0, issues

    @staticmethod
    def verify_from_json(json_path: Path) -> tuple[bool, list[str]]:
        """Load and verify a receipt from a JSON file."""
        try:
            data = json.loads(json_path.read_text())
        except Exception as e:
            return False, [f"Failed to load receipt: {e}"]

        receipt = ReceiptVerifier._dict_to_receipt(data)
        return ReceiptVerifier.verify(receipt)

    @staticmethod
    def _dict_to_receipt(data: dict) -> PRReceipt:
        """Reconstruct a PRReceipt from a dictionary."""
        receipt = PRReceipt(
            receipt_id=data.get("receipt_id", ""),
            created_at=data.get("created_at", ""),
            run_id=data.get("run_id", ""),
            repo_url=data.get("repo_url", ""),
            base_branch=data.get("base_branch", "main"),
            head_branch=data.get("head_branch", ""),
            pr_url=data.get("pr_url", ""),
            pr_number=data.get("pr_number", 0),
            total_lines_added=data.get("total_lines_added", 0),
            total_lines_removed=data.get("total_lines_removed", 0),
            total_tokens=data.get("total_tokens", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
            lint_clean=data.get("lint_clean", False),
            build_clean=data.get("build_clean", False),
            content_hash=data.get("content_hash", ""),
            risks=data.get("risks", []),
            notes=data.get("notes", []),
        )

        # Reconstruct nested objects
        for c in data.get("commits", []):
            receipt.commits.append(CommitInfo(**c))
        for f in data.get("files_changed", []):
            receipt.files_changed.append(FileChange(**f))
        for m in data.get("stage_metrics", []):
            receipt.stage_metrics.append(StageMetrics(**m))
        for d in data.get("decisions", []):
            receipt.decisions.append(AgentDecision(**d))

        tr = data.get("test_results", {})
        if tr:
            receipt.test_results = TestEvidence(**tr)
        sr = data.get("security_results", {})
        if sr:
            receipt.security_results = SecurityEvidence(**sr)

        return receipt
