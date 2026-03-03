import pytest  # noqa: I001
from unittest.mock import MagicMock

from src.core.chat_pipeline import ChatPipeline

@pytest.mark.asyncio
async def test_resolve_model_synthesis():
    pipeline = ChatPipeline(chat_store=MagicMock())
  # noqa: W293
    # 1. Test synthesizable OpenRouter ID
    model_def, error = pipeline._resolve_model("openrouter/meta-llama/llama-3-70b-instruct", complexity=5)
    assert error is None
    assert model_def is not None
    assert model_def.id == "openrouter/meta-llama/llama-3-70b-instruct"
    assert model_def.provider.value == "openrouter"
  # noqa: W293
    # 2. Test synthesizable OpenAI ID
    model_def, error = pipeline._resolve_model("openai/gpt-5-turbo", complexity=5)
    assert error is None
    assert model_def is not None
    assert model_def.id == "openai/gpt-5-turbo"
    assert model_def.provider.value == "openai"
  # noqa: W293
    # 3. Test malformed ID
    model_def, error = pipeline._resolve_model("not-a-provider-just-model", complexity=5)
    assert model_def is None
    assert "Expected 'provider/model'" in error
  # noqa: W293
    # 4. Test unsupported provider
    model_def, error = pipeline._resolve_model("fakehq/super-model", complexity=5)
    assert model_def is None
    assert "Unsupported provider" in error
