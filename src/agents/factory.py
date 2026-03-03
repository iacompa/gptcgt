"""
Agent Factory.

Instantiates the correct agent subclass based on the provided ModelDefinition.
"""

from __future__ import annotations

from src.agents.anthropic import AnthropicAgent
from src.agents.base import AgentConfig, BaseAgent
from src.agents.cohere import CohereAgent
from src.agents.custom import CustomAgent
from src.agents.deepseek import DeepSeekAgent
from src.agents.google import GoogleAgent
from src.agents.groq import GroqAgent
from src.agents.mistral import MistralAgent
from src.agents.openai import OpenAIAgent
from src.agents.openrouter import OpenRouterAgent
from src.agents.xai import XAIAgent
from src.core.model_registry import ModelDefinition, Provider

# Maps enum to corresponding API key names in keychain
PROVIDER_KEY_MAP = {
    Provider.ANTHROPIC.value: "ANTHROPIC_API_KEY",
    Provider.OPENAI.value: "OPENAI_API_KEY",
    Provider.GOOGLE.value: "GEMINI_API_KEY",
    Provider.DEEPSEEK.value: "DEEPSEEK_API_KEY",
    Provider.XAI.value: "XAI_API_KEY",
    Provider.OPENROUTER.value: "OPENROUTER_API_KEY",
    Provider.MISTRAL.value: "MISTRAL_API_KEY",
    Provider.COHERE.value: "COHERE_API_KEY",
    Provider.GROQ.value: "GROQ_API_KEY",
    Provider.CUSTOM.value: "CUSTOM_API_KEY",
}


class AgentFactory:
    """Factory for creating provider-specific agent instances from a model definition."""

    @staticmethod
    def create_agent(
        model_def: ModelDefinition,
        system_prompt: str = "",
        api_key: str | None = None,
        base_url: str | None = None,
        extra_headers: dict | None = None,
    ) -> BaseAgent:
        """Create and return the correctly typed Agent."""
        config = AgentConfig(
            model_id=model_def.id,
            max_tokens=model_def.max_output_tokens,
            system_prompt=system_prompt,
            api_key=api_key,
            base_url=base_url,
            extra_headers=extra_headers,
            # Tools will be injected later by the command pipeline
        )

        if model_def.provider == Provider.ANTHROPIC:
            return AnthropicAgent(config)
        elif model_def.provider == Provider.OPENAI:
            return OpenAIAgent(config)
        elif model_def.provider == Provider.GOOGLE:
            return GoogleAgent(config)
        elif model_def.provider == Provider.DEEPSEEK:
            return DeepSeekAgent(config)
        elif model_def.provider == Provider.XAI:
            return XAIAgent(config)
        elif model_def.provider == Provider.OPENROUTER:
            return OpenRouterAgent(config)
        elif model_def.provider == Provider.MISTRAL:
            return MistralAgent(config)
        elif model_def.provider == Provider.COHERE:
            return CohereAgent(config)
        elif model_def.provider == Provider.GROQ:
            return GroqAgent(config)
        elif model_def.provider == Provider.CUSTOM:
            return CustomAgent(config)
        else:
            raise ValueError(f"Unknown provider: {model_def.provider}")
