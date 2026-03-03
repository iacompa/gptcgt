"""
Base Agent Interface.

Defines the contract for all provider-specific agents (Anthropic, OpenAI, Google, etc.).
Every agent must support async streaming, token counting, tool execution,
and yield AgentResponse chunks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator

from src.core.logger import get_logger

logger = get_logger("agents.base")


class ProviderException(Exception):
    """Normalized exception for provider APIs (rate limit, auth, context size)."""

    def __init__(self, error_type: str, message: str, provider: str = "unknown"):
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.provider = provider



@dataclass
class AgentConfig:
    """Configuration passed to every agent upon initialization."""

    model_id: str
    temperature: float = 0.7
    max_tokens: int = 8192
    top_p: float = 1.0
    system_prompt: str = ""
    tools: list[dict] = field(default_factory=list)
    timeout: float = 300.0
    api_key: str | None = None
    base_url: str | None = None
    extra_headers: dict | None = None


@dataclass
class ProviderCapabilities:
    """Capabilities supported by this provider/model."""

    supports_streaming: bool = True
    supports_tools: bool = True
    supports_vision: bool = False
    max_context: int = 8192


@dataclass
class AgentResponse:
    """A single chunk or final result yielded by an agent."""

    text: str = ""
    is_streaming: bool = True
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    error: str | None = None
    finish_reason: str | None = None


class BaseAgent(ABC):
    """Abstract base class for all AI provider agents."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = logger

    @property
    def capabilities(self):
        """Return the capabilities of this specific agent/model."""
        # Default flags, can be overridden by specific provider adapters
        return ProviderCapabilities(max_context=self.config.max_tokens)

    @abstractmethod
    async def chat_stream(self, messages: list[dict]) -> AsyncGenerator[AgentResponse, None]:
        """
        Stream a chat completion.

        Args:
            messages: List of LiteLLM/OpenAI formatted dicts [{"role": "user", "content": "hello"}]

        Yields:
            AgentResponse chunks containing partial text, tool calls, or usage data.

        """
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens for the specific model to manage context limits."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name (e.g., 'anthropic', 'openai')."""
        pass

    async def health_check(self) -> dict:
        """Verify API connectivity with a minimal request. Returns {"reachable": bool, "latency_ms": int|None, "error": str|None}."""  # noqa: E501
        import time

        start = time.monotonic()
        # Limit to 1 token to minimize cost
        original_max_tokens = self.config.max_tokens
        self.config.max_tokens = 1
        try:
            gen = self.chat_stream([{"role": "user", "content": "hi"}])
            try:
                async for response in gen:
                    if response.error:
                        return {
                            "reachable": False,
                            "latency_ms": int((time.monotonic() - start) * 1000),
                            "error": response.error[:100],
                        }
                    return {
                        "reachable": True,
                        "latency_ms": int((time.monotonic() - start) * 1000),
                        "error": None,
                    }
                return {
                    "reachable": False,
                    "latency_ms": int((time.monotonic() - start) * 1000),
                    "error": "No response received",
                }
            finally:
                await gen.aclose()
        except Exception as e:
            return {
                "reachable": False,
                "latency_ms": int((time.monotonic() - start) * 1000),
                "error": str(e)[:100],
            }
        finally:
            self.config.max_tokens = original_max_tokens
