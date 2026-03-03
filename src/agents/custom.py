"""Custom Agent Implementation."""

from __future__ import annotations

from typing import AsyncGenerator

import tiktoken

from src.agents.base import AgentResponse, BaseAgent
from src.agents.litellm_client import LiteLLMClient
from src.auth.keychain import KeyChainManager


class CustomAgent(BaseAgent):
    """Agent implementation for custom/third-party API models."""

    async def chat_stream(self, messages: list[dict]) -> AsyncGenerator[AgentResponse, None]:
        # Custom models allow skipping API Keys if they're Local LLMs
        api_key = self.config.api_key or KeyChainManager.get_key("CUSTOM_API_KEY")

        # The model ID from config is directly used, as base_url and api_key are now dynamic
        # and LiteLLM can handle custom endpoints directly with base_url.
        # No need for custom_configs lookup or provider_prefix mapping.

        async for chunk in LiteLLMClient.stream(
            model=self.config.model_id,
            messages=messages,
            system_prompt=self.config.system_prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            tools=self.config.tools if self.config.tools else None,
            timeout=self.config.timeout,
            api_key=api_key,
            base_url=self.config.base_url,
            extra_headers=self.config.extra_headers,
        ):
            yield chunk

    def count_tokens(self, text: str) -> int:
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4

    def get_provider_name(self) -> str:
        return "custom"
