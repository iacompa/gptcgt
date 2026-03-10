"""Tests for Phase 3 — Replayable PR Receipts."""

import json

import pytest

from src.core.pr_receipt import (
    AgentDecision,
    CommitInfo,
    FileChange,
    PRReceipt,
    ReceiptGenerator,
    ReceiptVerifier,
    SecurityEvidence,
    StageMetrics,
    TestEvidence,
)

# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def sample_receipt() -> PRReceipt:
    """Create a populated receipt for testing."""
    receipt = PRReceipt(
        run_id="run-abc-123",
        repo_url="https://github.com/test/repo",
        base_branch="main",
        head_branch="gptcgt-auto",
        pr_url="https://github.com/test/repo/pull/42",
        pr_number=42,
    )

    receipt.commits = [
        CommitInfo(sha="abc123", message="Add auth module", timestamp="2024-01-01T00:00:00Z"),
        CommitInfo(sha="def456", message="Add tests", timestamp="2024-01-01T00:05:00Z"),
    ]

    receipt.files_changed = [
        FileChange(path="src/auth.py", action="created", lines_added=50, lines_removed=0, rationale="New auth module"),
        FileChange(path="tests/test_auth.py", action="created", lines_added=30, lines_removed=0, rationale="Tests"),
        FileChange(path="src/config.py", action="modified", lines_added=5, lines_removed=2, rationale="Wire auth"),
    ]

    receipt.test_results = TestEvidence(
        passed=12, failed=0, errors=0, coverage_percent=85.0,
        test_command="pytest tests/ -v", raw_output="12 passed"
    )

    receipt.security_results = SecurityEvidence(
        findings_count=0, critical=0, high=0, medium=0, low=0,
        scanner="custom+semgrep", badge="clean"
    )

    receipt.stage_metrics = [
        StageMetrics(stage="coder", tokens_in=1000, tokens_out=2000, cost_usd=0.015, duration_seconds=5.2, model="gpt-4"),
        StageMetrics(stage="tester", tokens_in=500, tokens_out=800, cost_usd=0.005, duration_seconds=3.1, model="gpt-4"),
        StageMetrics(stage="arbiter", tokens_in=300, tokens_out=200, cost_usd=0.003, duration_seconds=1.5, model="gpt-4"),
    ]

    receipt.decisions = [
        AgentDecision(agent="coder", action="Created auth module", reasoning="Required by scope", iteration=1),
        AgentDecision(agent="arbiter", action="Approved patch", reasoning="Tests pass, security clean", iteration=1),
    ]

    receipt.lint_clean = True
    receipt.build_clean = True
    receipt.risks = ["New dependency on PyJWT"]

    return receipt


# ── PRReceipt Tests ─────────────────────────────────────────────────────

class TestPRReceipt:
    """Test PRReceipt dataclass."""

    def test_compute_hash_deterministic(self, sample_receipt):
        hash1 = sample_receipt.compute_hash()
        hash2 = sample_receipt.compute_hash()
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex

    def test_compute_hash_changes_on_modification(self, sample_receipt):
        hash1 = sample_receipt.compute_hash()
        sample_receipt.pr_number = 99
        hash2 = sample_receipt.compute_hash()
        assert hash1 != hash2

    def test_to_dict_roundtrip(self, sample_receipt):
        d = sample_receipt.to_dict()
        assert d["run_id"] == "run-abc-123"
        assert d["pr_number"] == 42
        assert len(d["files_changed"]) == 3
        assert len(d["stage_metrics"]) == 3

    def test_summary_property(self, sample_receipt):
        sample_receipt.total_lines_added = 85
        sample_receipt.total_lines_removed = 2
        sample_receipt.total_cost_usd = 0.023
        summary = sample_receipt.summary
        assert "PR #42" in summary
        assert "3 files" in summary
        assert "+85/-2" in summary


# ── ReceiptGenerator Tests ──────────────────────────────────────────────

class TestReceiptGenerator:
    """Test receipt artifact generation."""

    def test_finalize_computes_totals(self, sample_receipt):
        gen = ReceiptGenerator(sample_receipt)
        result = gen.finalize()
        assert result.total_lines_added == 85  # 50 + 30 + 5
        assert result.total_lines_removed == 2
        assert result.total_tokens == 4800  # 1000+2000 + 500+800 + 300+200
        assert abs(result.total_cost_usd - 0.023) < 0.001

    def test_finalize_sets_receipt_id(self, sample_receipt):
        sample_receipt.receipt_id = ""
        gen = ReceiptGenerator(sample_receipt)
        result = gen.finalize()
        assert result.receipt_id != ""
        assert len(result.receipt_id) == 16

    def test_finalize_sets_content_hash(self, sample_receipt):
        gen = ReceiptGenerator(sample_receipt)
        result = gen.finalize()
        assert result.content_hash != ""
        assert len(result.content_hash) == 64

    def test_generate_all_creates_files(self, sample_receipt, tmp_path):
        gen = ReceiptGenerator(sample_receipt)
        artifacts = gen.generate_all(tmp_path / "receipt")
        assert len(artifacts) == 4
        assert (tmp_path / "receipt" / "pr_receipt.json").exists()
        assert (tmp_path / "receipt" / "pr_receipt.md").exists()
        assert (tmp_path / "receipt" / "verification_bundle.json").exists()
        assert (tmp_path / "receipt" / "replay.sh").exists()

    def test_json_receipt_is_valid(self, sample_receipt, tmp_path):
        gen = ReceiptGenerator(sample_receipt)
        artifacts = gen.generate_all(tmp_path / "receipt")
        data = json.loads(artifacts["pr_receipt.json"])
        assert data["run_id"] == "run-abc-123"
        assert data["content_hash"] != ""

    def test_markdown_receipt_format(self, sample_receipt, tmp_path):
        gen = ReceiptGenerator(sample_receipt)
        artifacts = gen.generate_all(tmp_path / "receipt")
        md = artifacts["pr_receipt.md"]
        assert "# PR Receipt" in md
        assert "Content Hash" in md
        assert "Files Changed" in md
        assert "Cost Breakdown" in md
        assert "src/auth.py" in md

    def test_replay_script_executable(self, sample_receipt, tmp_path):
        gen = ReceiptGenerator(sample_receipt)
        gen.generate_all(tmp_path / "receipt")
        replay_path = tmp_path / "receipt" / "replay.sh"
        import os
        assert os.access(replay_path, os.X_OK)

    def test_replay_script_content(self, sample_receipt, tmp_path):
        gen = ReceiptGenerator(sample_receipt)
        artifacts = gen.generate_all(tmp_path / "receipt")
        script = artifacts["replay.sh"]
        assert "#!/usr/bin/env bash" in script
        assert "set -euo pipefail" in script
        assert "git clone" in script
        assert "cherry-pick" in script
        assert "pytest" in script.lower() or "ruff" in script.lower()

    def test_verification_bundle_structure(self, sample_receipt, tmp_path):
        gen = ReceiptGenerator(sample_receipt)
        artifacts = gen.generate_all(tmp_path / "receipt")
        bundle = json.loads(artifacts["verification_bundle.json"])
        assert "receipt_id" in bundle
        assert "content_hash" in bundle
        assert "test_evidence" in bundle
        assert "security_evidence" in bundle
        assert bundle["lint_clean"] is True


# ── ReceiptVerifier Tests ───────────────────────────────────────────────

class TestReceiptVerifier:
    """Test receipt integrity verification."""

    def test_valid_receipt_passes(self, sample_receipt):
        gen = ReceiptGenerator(sample_receipt)
        receipt = gen.finalize()
        valid, issues = ReceiptVerifier.verify(receipt)
        assert valid, f"Unexpected issues: {issues}"
        assert len(issues) == 0

    def test_tampered_hash_detected(self, sample_receipt):
        gen = ReceiptGenerator(sample_receipt)
        receipt = gen.finalize()
        receipt.content_hash = "deadbeef" * 8
        valid, issues = ReceiptVerifier.verify(receipt)
        assert not valid
        assert any("hash mismatch" in i.lower() for i in issues)

    def test_inconsistent_totals_detected(self, sample_receipt):
        gen = ReceiptGenerator(sample_receipt)
        receipt = gen.finalize()
        # Tamper with totals without updating hash
        receipt.content_hash = ""  # Clear hash to avoid hash check
        receipt.total_lines_added = 999  # Wrong
        valid, issues = ReceiptVerifier.verify(receipt)
        assert not valid
        assert any("lines added mismatch" in i.lower() for i in issues)

    def test_missing_run_id_detected(self):
        receipt = PRReceipt()  # Empty receipt
        valid, issues = ReceiptVerifier.verify(receipt)
        assert not valid
        assert any("missing run_id" in i.lower() for i in issues)

    def test_verify_from_json_roundtrip(self, sample_receipt, tmp_path):
        gen = ReceiptGenerator(sample_receipt)
        gen.generate_all(tmp_path / "receipt")
        json_path = tmp_path / "receipt" / "pr_receipt.json"
        valid, issues = ReceiptVerifier.verify_from_json(json_path)
        assert valid, f"Unexpected issues: {issues}"

    def test_verify_from_json_invalid_file(self, tmp_path):
        bad_path = tmp_path / "nonexistent.json"
        valid, issues = ReceiptVerifier.verify_from_json(bad_path)
        assert not valid
        assert len(issues) > 0
