"""OpenAI Agent Implementation."""

from __future__ import annotations

from typing import AsyncGenerator

import tiktoken

from src.agents.base import AgentResponse, BaseAgent
from src.agents.litellm_client import LiteLLMClient
from src.auth.keychain import KeyChainManager


class OpenAIAgent(BaseAgent):
    """Agent implementation for OpenAI models."""

    @property
    def capabilities(self):
        from src.agents.base import ProviderCapabilities
        caps = ProviderCapabilities(max_context=self.config.max_tokens or 128000)
        # o1 models do not support streaming or tools currently
        if self.config.model_id.startswith("openai/o1"):
            caps.supports_streaming = False
            caps.supports_tools = False
        return caps

    async def chat_stream(self, messages: list[dict]) -> AsyncGenerator[AgentResponse, None]:
        api_key = self.config.api_key or KeyChainManager.get_key("OPENAI_API_KEY")
        if not api_key:
            yield AgentResponse(error="OPENAI_API_KEY not found in keychain.", is_streaming=False)
            return

        # Handle o1/o3 specifically: max_tokens -> max_completion_tokens (litellm handles this usually, but we set reasoning_effort)  # noqa: E501
        kwargs = {
            "model": self.config.model_id,
            "messages": messages,
            "temperature": self.config.temperature,
            "timeout": self.config.timeout,
            "api_key": api_key,
            "base_url": self.config.base_url,
        }
        if self.config.extra_headers:
            kwargs["extra_headers"] = self.config.extra_headers

        if self.config.model_id.startswith("openai/o3") or self.config.model_id.startswith(
            "openai/o1"
        ):
            if self.config.max_tokens:
                kwargs["max_completion_tokens"] = self.config.max_tokens
            if "temperature" in kwargs:
                del kwargs["temperature"]
            # reasoning_effort can be configured via litellm if we had a field, but litellm handles o1/o3 params well.  # noqa: E501
            # We must NOT pass system_prompt as a separate arg to stream() for o1/o3 if not supported, but LiteLLM handles the mapping.  # noqa: E501
        else:
            kwargs["system_prompt"] = self.config.system_prompt
            if self.config.max_tokens:
                kwargs["max_tokens"] = self.config.max_tokens

        if self.config.tools:
            kwargs["tools"] = self.config.tools

        async for chunk in LiteLLMClient.stream(**kwargs):
            yield chunk

    def count_tokens(self, text: str) -> int:
        try:
            # Usually cl100k_base or o200k_base depending on model (gpt-4o uses o200k_base)
            model_name = self.config.model_id.split("/")[-1]
            try:
                enc = tiktoken.encoding_for_model(model_name)
            except KeyError:
                if "gpt-4o" in model_name or "o1" in model_name or "o3" in model_name:
                    enc = tiktoken.get_encoding("o200k_base")
                else:
                    enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4

    def get_provider_name(self) -> str:
        return "openai"
