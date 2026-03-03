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

    @pytest.mark.asyncio
    @patch("src.core.config.ConfigManager")
    @patch("src.agents.factory.AgentFactory.create_agent")
    @patch("src.auth.keychain.KeyChainManager.get_key", return_value="fake_key")
    async def test_generate_and_run_honors_override(self, mock_get_key, mock_create, mock_config_cls):
        """Tester configures itself with the user's tester_model from config."""
        from src.core.model_registry import ModelDefinition, Provider
  # noqa: W293
        # Setup mock models
        cheap_model = ModelDefinition(id="openai/gpt-3.5-turbo", name="GPT-3.5", provider=Provider.OPENAI, input_cost_per_mtok=1.0, output_cost_per_mtok=2.0, max_context_tokens=8192)  # noqa: E501
        override_model = ModelDefinition(id="anthropic/claude-3-opus", name="Opus", provider=Provider.ANTHROPIC, input_cost_per_mtok=15.0, output_cost_per_mtok=75.0, max_context_tokens=200000)  # noqa: E501
  # noqa: W293
        agent = TesterAgent()
  # noqa: W293
        # Setup configs
        mock_config = mock_config_cls.return_value
        mock_config.user.tester_model = "anthropic/claude-3-opus"
  # noqa: W293
        # Create a mock agent instance that doesn't blow up on the loop
        mock_agent_instance = mock_create.return_value
  # noqa: W293
        async def mock_stream(*args, **kwargs):
            from src.agents.base import AgentResponse
            yield AgentResponse(text="def test_foo(): pass")
  # noqa: W293
        mock_agent_instance.chat_stream = mock_stream
  # noqa: W293
        test_code = await agent._generate_tests_multi_turn([], "python", [cheap_model, override_model])
  # noqa: W293
        # Assertion
        assert "def test_foo(): pass" in test_code
        mock_create.assert_called_once_with(override_model, api_key="fake_key", base_url=None)

    @pytest.mark.asyncio
    @patch("src.core.config.ConfigManager")
    @patch("src.agents.factory.AgentFactory.create_agent")
    @patch("src.auth.keychain.KeyChainManager.get_key", return_value="fake_key")
    async def test_generate_and_run_falls_back(self, mock_get_key, mock_create, mock_config_cls):
        """Tester falls back to cheapest model if override is missing or invalid."""
        from src.core.model_registry import ModelDefinition, Provider
  # noqa: W293
        cheap_model = ModelDefinition(id="openai/gpt-3.5-turbo", name="GPT-3.5", provider=Provider.OPENAI, input_cost_per_mtok=1.0, output_cost_per_mtok=2.0, max_context_tokens=8192)  # noqa: E501
        expensive_model = ModelDefinition(id="openai/gpt-4", name="GPT-4", provider=Provider.OPENAI, input_cost_per_mtok=10.0, output_cost_per_mtok=30.0, max_context_tokens=8192)  # noqa: E501
  # noqa: W293
        agent = TesterAgent()
  # noqa: W293
        mock_config = mock_config_cls.return_value
        mock_config.user.tester_model = "invalid-model/not-found"
  # noqa: W293
        mock_agent_instance = mock_create.return_value
        async def mock_stream(*args, **kwargs):
            from src.agents.base import AgentResponse
            yield AgentResponse(text="def test_bar(): pass")
        mock_agent_instance.chat_stream = mock_stream
  # noqa: W293
        test_code = await agent._generate_tests_multi_turn([], "python", [expensive_model, cheap_model])
  # noqa: W293
        # Assertion
        assert "def test_bar(): pass" in test_code
        mock_create.assert_called_once_with(cheap_model, api_key="fake_key", base_url=None)

