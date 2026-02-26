"""OpenRouter Agent Implementation."""

from __future__ import annotations

from typing import AsyncGenerator

import tiktoken

from src.agents.base import AgentResponse, BaseAgent
from src.agents.litellm_client import LiteLLMClient
from src.auth.keychain import KeyChainManager


class OpenRouterAgent(BaseAgent):
    """Agent implementation for OpenRouter models."""

    async def chat_stream(self, messages: list[dict]) -> AsyncGenerator[AgentResponse, None]:
        api_key = self.config.api_key or KeyChainManager.get_key("OPENROUTER_API_KEY")
        if not api_key:
            yield AgentResponse(error="OPENROUTER_API_KEY not found in keychain.", is_streaming=False)
            return

        kwargs = {
            "model": self.config.model_id,
            "messages": messages,
            "system_prompt": self.config.system_prompt,
            "temperature": self.config.temperature,
            "timeout": self.config.timeout,
            "api_key": api_key,
            "base_url": self.config.base_url,
            "extra_headers": {
                "HTTP-Referer": "https://gptcgt.ai",
                "X-Title": "gptcgt Terminal IDE",
            }
        }

        if self.config.max_tokens:
            kwargs["max_tokens"] = self.config.max_tokens

        if self.config.tools:
            kwargs["tools"] = self.config.tools

        async for chunk in LiteLLMClient.stream(**kwargs):
            yield chunk

    def count_tokens(self, text: str) -> int:
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4

    def get_provider_name(self) -> str:
        return "openrouter"
