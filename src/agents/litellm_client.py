"""
LiteLLM Client Integration.

Provides a unified interface to litellm.acompletion, handling auth keys,
streaming logic, and basic error recovery.
"""

from __future__ import annotations

from typing import AsyncGenerator

import litellm

from src.agents.base import AgentResponse
from src.core.logger import get_logger

logger = get_logger("agents.litellm")

# Disable litellm's noisy telemetry/logging by default
litellm.telemetry = False
litellm.set_verbose = False


class LiteLLMClient:
    """Wrapper around litellm's async streaming completion."""

    @staticmethod
    async def stream(
        model: str,
        messages: list[dict],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 8192,
        tools: list[dict] | None = None,
        timeout: float = 300.0,
        api_key: str | None = None,
        base_url: str | None = None,
        extra_headers: dict | None = None,
        **extra_kwargs,
    ) -> AsyncGenerator[AgentResponse, None]:
        """
        # noqa: D200
        Stream a completion from litellm.
        """
        # Inject system prompt as first message if provided
        request_messages = messages.copy()
        if system_prompt:
            # Check if there's already a system prompt
            if request_messages and request_messages[0].get("role") == "system":
                request_messages[0]["content"] = system_prompt
            else:
                request_messages.insert(0, {"role": "system", "content": system_prompt})

        # If a custom base URL (like our managed API proxy) is provided, LiteLLM requires
        # the 'openai/' prefix so it knows to send the request as a standard OpenAI
        # /v1/chat/completions payload to that proxy, rather than the native provider's format.
        if base_url and not model.startswith("openai/"):
            # Strip native provider prefixes if they exist (e.g., 'anthropic/claude...' -> 'openai/claude...')
            pure_model = model.split("/")[-1] if "/" in model else model
            model = f"openai/{pure_model}"

        kwargs = {
            "model": model,
            "messages": request_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
            "timeout": timeout,
            "api_key": api_key,
            **extra_kwargs,
        }

        if tools:
            kwargs["tools"] = tools

        if base_url:
            kwargs["api_base"] = base_url

        if extra_headers:
            kwargs["extra_headers"] = extra_headers

        logger.debug(f"Calling litellm.acompletion for model {model} (messages: {len(request_messages)})")

        import asyncio

        max_retries = 2
        base_wait = 2

        for attempt in range(max_retries):
            try:
                response = await litellm.acompletion(**kwargs)
                tool_calls_buffer = {}
                usage_data = {}

                async for chunk in response:
                    delta = chunk.choices[0].delta
                    is_streaming = True
                    chunk_text = ""
                    finish_reason = chunk.choices[0].finish_reason

                    if hasattr(delta, "content") and delta.content is not None:
                        chunk_text = delta.content

                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        for tc_chunk in delta.tool_calls:
                            idx = tc_chunk.index
                            if idx not in tool_calls_buffer:
                                tool_calls_buffer[idx] = {
                                    "id": tc_chunk.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc_chunk.function.name if tc_chunk.function.name else "",
                                        "arguments": tc_chunk.function.arguments if tc_chunk.function.arguments else "",
                                    },
                                }
                            else:
                                if tc_chunk.function.arguments:
                                    tool_calls_buffer[idx]["function"]["arguments"] += tc_chunk.function.arguments

                    if hasattr(chunk, "usage") and chunk.usage:
                        usage_data = {
                            "prompt_tokens": chunk.usage.prompt_tokens,
                            "completion_tokens": chunk.usage.completion_tokens,
                            "total_tokens": getattr(
                                chunk.usage,
                                "total_tokens",
                                chunk.usage.prompt_tokens + chunk.usage.completion_tokens,
                            ),
                        }

                    if finish_reason is not None:
                        is_streaming = False

                    yield AgentResponse(
                        text=chunk_text,
                        is_streaming=is_streaming,
                        tool_calls=list(tool_calls_buffer.values()) if not is_streaming and tool_calls_buffer else [],
                        usage=usage_data if not is_streaming else {},
                        finish_reason=finish_reason,
                    )
                break  # Success, exit retry loop

            except litellm.RateLimitError as e:
                if attempt == max_retries - 1:
                    logger.error(f"Rate limit exceeded (final attempt): {e}")
                    from src.agents.base import ProviderException

                    raise ProviderException(
                        error_type="rate_limit",
                        message=f"Rate limit exceeded after {max_retries} retries: {str(e)}",
                        provider=model.split("/")[0] if "/" in model else "unknown",
                    )

                wait_time = base_wait * (2**attempt)
                logger.warning(
                    f"Rate limit exceeded, retrying in {wait_time}s... (Attempt {attempt + 1}/{max_retries})"  # noqa: E501
                )
                await asyncio.sleep(wait_time)
            except litellm.AuthenticationError as e:
                logger.error(f"Authentication failed: {e}")
                from src.agents.base import ProviderException

                raise ProviderException(
                    error_type="auth_error",
                    message=f"Authentication failed. Check your API key. ({str(e)})",
                    provider=model.split("/")[0] if "/" in model else "unknown",
                )
            except litellm.ContextWindowExceededError as e:
                logger.error(f"Context window exceeded: {e}")
                from src.agents.base import ProviderException

                raise ProviderException(
                    error_type="context_window_exceeded",
                    message=f"Context window exceeded. Please clear chat or trim files. ({str(e)})",
                    provider=model.split("/")[0] if "/" in model else "unknown",
                )
            except Exception as e:
                logger.exception(f"Unexpected litellm error: {e}")
                from src.agents.base import ProviderException

                raise ProviderException(
                    error_type="unknown",
                    message=f"Model error: {str(e)}",
                    provider=model.split("/")[0] if "/" in model else "unknown",
                )
