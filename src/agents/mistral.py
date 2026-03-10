"""Mistral Agent Implementation."""

from __future__ import annotations

from typing import AsyncGenerator

import tiktoken

from src.agents.base import AgentResponse, BaseAgent
from src.agents.litellm_client import LiteLLMClient
from src.auth.keychain import KeyChainManager


class MistralAgent(BaseAgent):
    """Agent implementation for Mistral models."""

    async def chat_stream(self, messages: list[dict]) -> AsyncGenerator[AgentResponse, None]:
        api_key = self.config.api_key or KeyChainManager.get_key("MISTRAL_API_KEY")
        if not api_key:
            yield AgentResponse(error="MISTRAL_API_KEY not found in keychain.", is_streaming=False)
            return

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
        """Mistral uses a slightly larger token ratio (~1.05x cl100k_base)."""
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return int(len(enc.encode(text)) * 1.05)
        except Exception:
            return len(text) // 3

    def get_provider_name(self) -> str:
        return "mistral"
