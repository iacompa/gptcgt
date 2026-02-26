"""Tests for self-healing verification contract — ensures correct VerificationResult attrs."""

import inspect

from src.tools.sandbox import TestResult as SandboxTestResult


class TestSelfHealingContract:
    """Verify chat_pipeline uses correct VerificationResult attributes."""

    def test_no_invalid_verdict_attrs(self):
        """Self-healing should NOT use verdict.tests_passed or verdict.test_failures."""
        from src.core import chat_pipeline
        source = inspect.getsource(chat_pipeline)
        assert "verdict.tests_passed" not in source, (
            "chat_pipeline still uses invalid 'verdict.tests_passed'"
        )
        assert "verdict.test_failures" not in source, (
            "chat_pipeline still uses invalid 'verdict.test_failures'"
        )

    def test_uses_correct_attrs(self):
        """Self-healing should use verdict.test_result.all_passed and .failures."""
        from src.core import chat_pipeline
        source = inspect.getsource(chat_pipeline)
        assert "test_result" in source, (
            "chat_pipeline does not reference test_result"
        )

    def test_verification_result_has_correct_fields(self):
        """VerificationResult from sandbox must have test_result field."""
        from src.tools.sandbox import VerificationResult
        v = VerificationResult(agent_id="test", model_name="test")
        assert hasattr(v, "test_result")
        assert hasattr(v, "syntax_valid")
        assert hasattr(v, "lint_result")
        assert hasattr(v, "security_findings")

    def test_test_result_has_correct_api(self):
        """TestResult must have passed, failed, failures, all_passed."""
        t = SandboxTestResult(total=5, passed=3, failed=2)
        assert t.passed == 3
        assert t.failed == 2
        assert hasattr(t, "failures")
        assert hasattr(t, "all_passed")
        assert t.all_passed is False

    def test_test_result_all_passed_true(self):
        t = SandboxTestResult(total=5, passed=5, failed=0)
        assert t.all_passed is True
