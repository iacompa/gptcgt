"""Tests for Phase 1: Verified PR Mode — ProofBundle, ProofRunner, ProofValidator."""

import time


def test_proof_bundle_verified():
    """All checks passed → VERIFIED."""
    from src.core.proof import CheckResult, ProofBundle, Verdict

    bundle = ProofBundle(run_id="run-1", commit_sha="abc123")
    bundle.tests = CheckResult(name="tests", passed=True)
    bundle.lint = CheckResult(name="lint", passed=True)
    bundle.security = CheckResult(name="security", passed=True)
    bundle.migration = CheckResult(name="migration", passed=True)

    assert bundle.recompute_verdict() == Verdict.VERIFIED


def test_proof_bundle_partial():
    """One check skipped → PARTIAL."""
    from src.core.proof import CheckResult, ProofBundle, Verdict

    bundle = ProofBundle(run_id="run-2", commit_sha="def456")
    bundle.tests = CheckResult(name="tests", passed=True)
    bundle.lint = CheckResult(name="lint", passed=True)
    bundle.security = CheckResult(name="security", passed=True, skipped=True)
    bundle.migration = CheckResult(name="migration", passed=True)

    assert bundle.recompute_verdict() == Verdict.PARTIAL


def test_proof_bundle_blocked():
    """One check failed → BLOCKED."""
    from src.core.proof import CheckResult, ProofBundle, Verdict

    bundle = ProofBundle(run_id="run-3", commit_sha="ghi789")
    bundle.tests = CheckResult(name="tests", passed=False, error="2 failures")
    bundle.lint = CheckResult(name="lint", passed=True)
    bundle.security = CheckResult(name="security", passed=True)
    bundle.migration = CheckResult(name="migration", passed=True)

    assert bundle.recompute_verdict() == Verdict.BLOCKED


def test_proof_validator_blocks_unverified():
    """ProofValidator blocks PR for failed bundle."""
    from src.core.proof import CheckResult, ProofBundle, ProofValidator

    bundle = ProofBundle(run_id="x")
    bundle.tests = CheckResult(name="tests", passed=False)
    bundle.lint = CheckResult(name="lint", passed=True)
    bundle.security = CheckResult(name="security", passed=True)
    bundle.migration = CheckResult(name="migration", passed=True)

    allowed, reason = ProofValidator.validate(bundle)
    assert allowed is False
    assert "tests" in reason


def test_proof_validator_allows_verified():
    """ProofValidator allows PR for verified bundle."""
    from src.core.proof import CheckResult, ProofBundle, ProofValidator

    bundle = ProofBundle(run_id="x")
    bundle.tests = CheckResult(name="tests", passed=True)
    bundle.lint = CheckResult(name="lint", passed=True)
    bundle.security = CheckResult(name="security", passed=True)
    bundle.migration = CheckResult(name="migration", passed=True)

    allowed, reason = ProofValidator.validate(bundle)
    assert allowed is True


def test_proof_validator_stale_detection():
    """Stale bundles are detected."""
    from src.core.proof import ProofBundle, ProofValidator

    bundle = ProofBundle(run_id="x", timestamp=time.time() - 700)
    assert ProofValidator.is_stale(bundle, max_age_sec=600) is True

    fresh = ProofBundle(run_id="y", timestamp=time.time())
    assert ProofValidator.is_stale(fresh, max_age_sec=600) is False


def test_proof_bundle_summary():
    """Summary contains meaningful information."""
    from src.core.proof import CheckResult, ProofBundle

    bundle = ProofBundle(run_id="s", cost_delta_usd=0.0234)
    bundle.tests = CheckResult(name="tests", passed=True)
    bundle.lint = CheckResult(name="lint", passed=False, error="3 errors")
    bundle.security = CheckResult(name="security", passed=True)
    bundle.migration = CheckResult(name="migration", passed=True)
    bundle.recompute_verdict()

    assert "BLOCKED" in bundle.summary
    assert "lint" in bundle.summary
    assert "$0.0234" in bundle.summary


def test_proof_bundle_json_serialization():
    """ProofBundle serializes to valid JSON."""
    import json

    from src.core.proof import CheckResult, ProofBundle

    bundle = ProofBundle(run_id="j", commit_sha="sha")
    bundle.tests = CheckResult(name="tests", passed=True)
    bundle.lint = CheckResult(name="lint", passed=True)
    bundle.security = CheckResult(name="security", passed=True)
    bundle.migration = CheckResult(name="migration", passed=True)
    bundle.recompute_verdict()

    data = json.loads(bundle.to_json())
    assert data["run_id"] == "j"
    assert data["verdict"] == "verified"
