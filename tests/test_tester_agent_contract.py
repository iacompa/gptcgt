"""Tests for TesterAgent contract — verifies it uses correct E2BSandbox API."""

from unittest.mock import patch

import pytest

from src.agents.tester_agent import TesterAgent, TestResult


class TestTestResultDataclass:
    def test_pass_rate_all_pass(self):
        r = TestResult(passed=10, failed=0, errors=0)
        assert r.pass_rate == 100.0

    def test_pass_rate_mixed(self):
        r = TestResult(passed=7, failed=2, errors=1)
        assert r.pass_rate == 70.0

    def test_pass_rate_zero_total(self):
        r = TestResult(passed=0, failed=0, errors=0)
        assert r.pass_rate == 0.0

    def test_failure_details_default_empty(self):
        r = TestResult()
        assert r.failure_details == []
        assert r.generated_test_code == ""


class TestTesterAgentContract:
    """Verify TesterAgent uses verify_patch (not run_test) and correct field names."""

    def test_no_run_test_attribute(self):
        """TesterAgent should NEVER call sandbox.run_test — it doesn't exist."""
        import inspect
        source = inspect.getsource(TesterAgent)
        assert "sandbox.run_test" not in source, "TesterAgent still references non-existent sandbox.run_test"

    def test_uses_verify_patch(self):
        """TesterAgent should use sandbox.verify_patch."""
        import inspect
        source = inspect.getsource(TesterAgent)
        assert "verify_patch" in source, "TesterAgent does not use verify_patch"

    def test_uses_correct_field_names(self):
        """TesterAgent should read .passed, .failed, .failures — not tests_passed etc."""
        import inspect
        source = inspect.getsource(TesterAgent)
        assert "tests_passed" not in source, "TesterAgent uses wrong field 'tests_passed'"
        assert "tests_failed" not in source, "TesterAgent uses wrong field 'tests_failed'"
        assert "test_failures" not in source, "TesterAgent uses wrong field 'test_failures'"

    @pytest.mark.asyncio
    async def test_generate_and_run_handles_no_models(self):
        """When no models available, returns empty TestResult gracefully."""
        agent = TesterAgent()
        with patch.object(agent.registry, "get_available_models", return_value=[]):
            result = await agent.generate_and_run_tests("+ added line", "python")
        assert result.passed == 0
        assert result.generated_test_code == ""
