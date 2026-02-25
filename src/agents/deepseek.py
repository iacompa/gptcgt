"""DeepSeek Agent Implementation."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import tiktoken

from src.agents.base import AgentResponse, BaseAgent
from src.agents.litellm_client import LiteLLMClient
from src.auth.keychain import KeyChainManager

_residency_lock = asyncio.Lock()
_residency_warned = False


class DeepSeekAgent(BaseAgent):
    """Agent implementation for DeepSeek models."""

    async def chat_stream(self, messages: list[dict]) -> AsyncGenerator[AgentResponse, None]:
        global _residency_warned
        async with _residency_lock:
            if not _residency_warned:
                self.logger.info(
                    "DeepSeek processes requests on servers in China. See gptcgt.ai/legal/privacy for details."  # noqa: E501
                )
                _residency_warned = True

        api_key = self.config.api_key or KeyChainManager.get_key("DEEPSEEK_API_KEY")
        if not api_key:
            yield AgentResponse(error="DEEPSEEK_API_KEY not found in keychain.", is_streaming=False)
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
        ):
            yield chunk

    def count_tokens(self, text: str) -> int:
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4

    def get_provider_name(self) -> str:
        return "deepseek"
