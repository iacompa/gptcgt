# ruff: noqa: E501

"""
Model registry — catalog of all available AI models.

Every model has: ID, provider, pricing, context limits, capabilities,
and quality tier assignments. Loaded from bundled JSON on startup.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger("core.model_registry")


class Provider(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    XAI = "xai"
    DEEPSEEK = "deepseek"
    OPENROUTER = "openrouter"
    CUSTOM = "custom"


class QualityTier(Enum):
    LIGHT = "light"  # Budget models — cheapest option
    STANDARD = "standard"  # Best cost/performance ratio
    MAX = "max"  # Best available models


@dataclass
class ModelDefinition:
    """Complete definition of an AI model."""

    # Identity
    id: str  # LiteLLM model string: "anthropic/claude-sonnet-4-20250514"
    name: str  # Human name: "Claude Sonnet 4"
    provider: Provider

    # Pricing (per million tokens, USD)
    input_cost_per_mtok: float
    output_cost_per_mtok: float

    # Context window
    max_context_tokens: int  # Total context window (e.g., 200000)

    cache_read_cost_per_mtok: float = 0.0
    cache_write_cost_per_mtok: float = 0.0
    max_output_tokens: int = 8192  # Max tokens model can generate

    # Capabilities
    supports_streaming: bool = True
    supports_images: bool = False
    supports_tool_use: bool = False

    # Quality tier assignments (a model can belong to multiple tiers)
    quality_tiers: list[str] = field(default_factory=list)  # ["light", "standard"]

    # UI display
    display_color: str = "#FFFFFF"
    display_emoji: str = "🤖"

    # Status
    deprecated: bool = False
    deprecation_message: str = ""


class ModelRegistry:
    """
    Singleton registry of all available AI models.

    Data sources (loaded in order, later overrides earlier):
    1. Bundled defaults — src/data/models.json (ships with app)
    2. Custom models — .gptcgt/config.toml [custom_models] section

    Key methods:
        registry.get(model_id) → ModelDefinition | None
        registry.get_models_for_tier(QualityTier.LIGHT) → [ModelDefinition, ...]
        registry.get_cheapest_model() → ModelDefinition
        registry.get_by_provider(Provider.ANTHROPIC) → [ModelDefinition, ...]
        registry.get_available_models() → [ModelDefinition, ...]  # Has API keys (checks KeychainManager)  # noqa: E501
        registry.get_default_for_tier(tier) → ModelDefinition
        registry.calculate_cost(model_id, input_tokens, output_tokens) → float
        registry.register_custom_model(model_def) → None
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._models: dict[str, ModelDefinition] = {}
            cls._instance._loaded = False
        return cls._instance

    def load(
        self, bundled_path: Path | None = None, custom_models: list[dict] | None = None
    ) -> None:
        """Load models from bundled JSON, then overlay custom models."""
        if bundled_path is None:
            bundled_path = Path(__file__).parent.parent / "data" / "models.json"

        # Phase 11: Dynamic Price Syncing
        import urllib.request

        dynamic_prices = {}
        try:
            # 1.5s timeout prevents blocking app boot if offline
            url = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=1.5) as response:
                if response.status == 200:
                    dynamic_prices = json.loads(response.read().decode())
                    logger.info("Successfully fetched dynamic model pricing from LiteLLM.")
        except Exception as e:
            logger.warning(
                f"Could not fetch dynamic model pricing, falling back to static rates: {e}"
            )

        if bundled_path.exists():
            with open(bundled_path) as f:
                data = json.load(f)
            for entry in data.get("models", []):
                try:
                    provider = Provider(entry["provider"])

                    # Apply dynamic prices if available
                    in_cost = entry["input_cost_per_mtok"]
                    out_cost = entry["output_cost_per_mtok"]
                    if entry["id"] in dynamic_prices:
                        dyn_data = dynamic_prices[entry["id"]]
                        in_cost = (
                            dyn_data.get("input_cost_per_token", in_cost / 1_000_000) * 1_000_000
                        )
                        out_cost = (
                            dyn_data.get("output_cost_per_token", out_cost / 1_000_000) * 1_000_000
                        )

                    model = ModelDefinition(
                        id=entry["id"],
                        name=entry["name"],
                        provider=provider,
                        input_cost_per_mtok=in_cost,
                        output_cost_per_mtok=out_cost,
                        cache_read_cost_per_mtok=entry.get("cache_read_cost_per_mtok", 0.0),
                        cache_write_cost_per_mtok=entry.get("cache_write_cost_per_mtok", 0.0),
                        max_context_tokens=entry["max_context_tokens"],
                        max_output_tokens=entry.get("max_output_tokens", 8192),
                        supports_streaming=entry.get("supports_streaming", True),
                        supports_images=entry.get("supports_images", False),
                        supports_tool_use=entry.get("supports_tool_use", False),
                        quality_tiers=entry.get("quality_tiers", []),
                        display_color=entry.get("display_color", "#FFFFFF"),
                        display_emoji=entry.get("display_emoji", "🤖"),
                        deprecated=entry.get("deprecated", False),
                        deprecation_message=entry.get("deprecation_message", ""),
                    )
                    self._models[model.id] = model
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping malformed model entry: {e}")

        # Overlay custom models
        if custom_models:
            for entry in custom_models:
                try:
                    model = ModelDefinition(
                        id=entry["id"],
                        name=entry.get("name", entry["id"]),
                        provider=Provider.CUSTOM,
                        input_cost_per_mtok=entry.get("input_cost_per_mtok", 0.0),
                        output_cost_per_mtok=entry.get("output_cost_per_mtok", 0.0),
                        max_context_tokens=entry.get("max_context_tokens", 32000),
                        max_output_tokens=entry.get("max_output_tokens", 4096),
                        quality_tiers=entry.get("quality_tiers", ["standard"]),
                        display_color=entry.get("display_color", "#FF8800"),
                        display_emoji="🔧",
                    )
                    self._models[model.id] = model
                    logger.info(f"Registered custom model: {model.id}")
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping malformed custom model: {e}")

        self._loaded = True
        logger.info(f"Model registry loaded: {len(self._models)} models")

    def get(self, model_id: str) -> ModelDefinition | None:
        return self._models.get(model_id)

    def get_models_for_tier(self, tier: QualityTier) -> list[ModelDefinition]:
        return sorted(
            [
                m
                for m in self._models.values()
                if tier.value in m.quality_tiers and not m.deprecated
            ],
            key=lambda m: m.input_cost_per_mtok,
        )

    def get_cheapest_model(self) -> ModelDefinition:
        available = [m for m in self._models.values() if not m.deprecated]
        return min(available, key=lambda m: m.input_cost_per_mtok)

    def get_by_provider(self, provider: Provider) -> list[ModelDefinition]:
        return [m for m in self._models.values() if m.provider == provider and not m.deprecated]

    def get_available_models(self) -> list[ModelDefinition]:
        """
        Get models the user has API keys for.

        Uses KeychainManager (classmethod-based) with PROVIDER_API_KEY naming.
        """
        from src.agents.factory import PROVIDER_KEY_MAP
        from src.auth.keychain import KeyChainManager

        available = []
        for model in self._models.values():
            if model.deprecated:
                continue
            key_name = PROVIDER_KEY_MAP.get(model.provider.value)
            if key_name and KeyChainManager.get_key(key_name) is not None:
                available.append(model)
        return available

    def get_default_for_tier(self, tier: QualityTier) -> ModelDefinition | None:
        """Get the recommended default model for a tier that the user actually has keys for."""
        all_models_in_tier = self.get_models_for_tier(tier)
        available = self.get_available_models()

        # Filter tier models to only those we have keys for
        models = [m for m in all_models_in_tier if m in available]

        if not models:
            # Fallback to absolute defaults if no keys are found (e.g. for proxy routing or UI rendering before setup)
            models = all_models_in_tier
            if not models:
                return None

        # For LIGHT: cheapest. For STANDARD: best cost/performance. For MAX: best overall.
        if tier == QualityTier.MAX:
            return max(models, key=lambda m: m.input_cost_per_mtok)  # Most expensive = most capable
        return models[0]  # Cheapest in tier

    def calculate_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate USD cost for a specific usage."""
        model = self.get(model_id)
        if model is None:
            return 0.0
        input_cost = (input_tokens / 1_000_000) * model.input_cost_per_mtok
        output_cost = (output_tokens / 1_000_000) * model.output_cost_per_mtok
        return input_cost + output_cost

    def register_custom_model(self, model_def: ModelDefinition) -> None:
        self._models[model_def.id] = model_def

    async def fetch_openrouter_models(self) -> list[dict]:
        """Fetch real-time model list and pricing from OpenRouter."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("https://openrouter.ai/api/v1/models")
                response.raise_for_status()
                data = response.json().get("data", [])
                return data
        except Exception as e:
            logger.warning(f"Failed to fetch OpenRouter models: {e}")
            return []

    def register_custom_openrouter_model(self, model_id: str, name: str, tier: QualityTier, openrouter_data: list[dict] | None = None) -> None:
        """Register a dynamic OpenRouter model from API data."""
        # Enforce openrouter/ prefix for litellm
        if not model_id.startswith("openrouter/"):
            model_id = f"openrouter/{model_id}"

        in_cost = 0.0
        out_cost = 0.0
        max_context = 128000

        if openrouter_data:
            search_id = model_id.replace("openrouter/", "")
            for m in openrouter_data:
                if m.get("id") == search_id:
                    pricing = m.get("pricing", {})
                    try:
                        in_cost = float(pricing.get("prompt", 0)) * 1_000_000
                        out_cost = float(pricing.get("completion", 0)) * 1_000_000
                    except (ValueError, TypeError):
                        pass
                    max_context = m.get("context_length", max_context)
                    if not name:
                        name = m.get("name", search_id)
                    break

        if not name:
            name = model_id.split("/")[-1].replace("-", " ").title()

        model = ModelDefinition(
            id=model_id,
            name=name,
            provider=Provider.OPENROUTER,
            input_cost_per_mtok=in_cost,
            output_cost_per_mtok=out_cost,
            max_context_tokens=max_context,
            max_output_tokens=8192,
            quality_tiers=[tier.value],
            display_color="#3B82F6",
            display_emoji="🐋"
        )
        self._models[model_id] = model
        logger.info(f"Registered dynamic OpenRouter model: {model_id} (${in_cost:.2f} / ${out_cost:.2f})")

    def get_all(self) -> list[ModelDefinition]:
        return list(self._models.values())
