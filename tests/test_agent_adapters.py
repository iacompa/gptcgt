import pytest  # noqa: I001
from unittest.mock import patch, AsyncMock
from src.agents.base import AgentConfig
from src.agents.openai import OpenAIAgent
from src.agents.openrouter import OpenRouterAgent

@pytest.mark.asyncio
@patch("src.agents.openai.LiteLLMClient.stream")
@patch("src.agents.openai.KeyChainManager.get_key", return_value="fake-key")
async def test_openai_agent_header_propagation(mock_get_key, mock_stream):
    """Test that OpenAIAgent forwards custom headers down to kwargs."""  # noqa: D202
  # noqa: W293
    config = AgentConfig(
        model_id="openai/gpt-4o",
        extra_headers={"X-Custom-Test": "HelloWorld"}
    )
  # noqa: W293
    agent = OpenAIAgent(config)
  # noqa: W293
    mock_stream.return_value = AsyncMock()
  # noqa: W293
    # Run the generator just enough to trigger the litellm call
    async for _ in agent.chat_stream([]):
        break
  # noqa: W293
    mock_stream.assert_called_once()
    kwargs = mock_stream.call_args.kwargs
    assert "extra_headers" in kwargs
    assert kwargs["extra_headers"] == {"X-Custom-Test": "HelloWorld"}

@pytest.mark.asyncio
@patch("src.agents.openrouter.LiteLLMClient.stream")
@patch("src.agents.openrouter.KeyChainManager.get_key", return_value="fake-key")
async def test_openrouter_agent_header_merging(mock_get_key, mock_stream):
    """Test that OpenRouterAgent merges config headers with its default referrer headers."""  # noqa: D202
  # noqa: W293
    config = AgentConfig(
        model_id="openrouter/anthropic/claude-3-opus",
        extra_headers={"X-Custom-Test": "HelloWorld"}
    )
  # noqa: W293
    agent = OpenRouterAgent(config)
  # noqa: W293
    mock_stream.return_value = AsyncMock()
  # noqa: W293
    async for _ in agent.chat_stream([]):
        break
  # noqa: W293
    mock_stream.assert_called_once()
    kwargs = mock_stream.call_args.kwargs
    assert "extra_headers" in kwargs
    headers = kwargs["extra_headers"]
  # noqa: W293
    # Must contain both the default and the custom
    assert "HTTP-Referer" in headers
    assert "X-Title" in headers
    assert "X-Custom-Test" in headers
    assert headers["X-Custom-Test"] == "HelloWorld"
