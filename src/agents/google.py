"""Google Agent Implementation."""

from __future__ import annotations

from typing import AsyncGenerator

import tiktoken

from src.agents.base import AgentResponse, BaseAgent
from src.agents.litellm_client import LiteLLMClient
from src.auth.keychain import KeyChainManager


class GoogleAgent(BaseAgent):
    """Agent implementation for Google Gemini models."""

    async def chat_stream(self, messages: list[dict]) -> AsyncGenerator[AgentResponse, None]:
        api_key = self.config.api_key or KeyChainManager.get_key("GEMINI_API_KEY")
        if not api_key:
            yield AgentResponse(error="GEMINI_API_KEY not found in keychain.", is_streaming=False)
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
        # LiteLLM handles token counting properly via vertex/google libraries,
        # but locally we fall back to tiktoken heuristic for speed/offline context window checks.
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4

    def get_provider_name(self) -> str:
        return "google"
