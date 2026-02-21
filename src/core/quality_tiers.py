from dataclasses import dataclass
from enum import Enum


class QualityTier(Enum):
    """
    Three quality tiers controlling model selection.
    
    LIGHT: Cheapest models that can still complete the task.
    STANDARD: Best performance-to-cost ratio.
    MAX: Best available models for everything, regardless of cost.
    """
    LIGHT = "light"
    STANDARD = "standard"
    MAX = "max"


@dataclass
class TierConfig:
    """Configuration for a quality tier."""
    tier: QualityTier
    display_name: str
    description: str           # One-line explanation shown to user
    icon: str                  # Emoji for status bar
    color: str                 # Hex color for status bar display
    cost_multiplier: float     # Approximate cost relative to Standard (1.0)
    preferred_models: dict     # {"orchestrator": "model_id", "coding": ["model_id", ...]}


# Default tier configurations
TIER_CONFIGS: dict[QualityTier, TierConfig] = {
    QualityTier.LIGHT: TierConfig(
        tier=QualityTier.LIGHT,
        display_name="Light",
        description="Budget-friendly — cheapest capable models",
        icon="💡",
        color="#4ADE80",       # Soft green
        cost_multiplier=0.3,   # ~70% cheaper than Standard
        preferred_models={
            "orchestrator": "gemini-2.5-flash",
            "coding": ["deepseek-chat", "gpt-4o-mini", "gemini-2.5-flash"],
            "testing": ["deepseek-chat"],
        },
    ),
    QualityTier.STANDARD: TierConfig(
        tier=QualityTier.STANDARD,
        display_name="Standard",
        description="Best value — optimal performance-to-cost ratio",
        icon="⚡",
        color="#58A6FF",       # Blue (matches accent)
        cost_multiplier=1.0,   # Baseline
        preferred_models={
            "orchestrator": "gemini-2.5-pro",
            "coding": ["claude-3-5-sonnet", "gpt-4o", "gemini-2.5-pro"],
            "testing": ["gpt-4o-mini", "deepseek-chat"],
        },
    ),
    QualityTier.MAX: TierConfig(
        tier=QualityTier.MAX,
        display_name="Max",
        description="Maximum quality — premium models, best results",
        icon="🔥",
        color="#F59E0B",       # Amber/gold
        cost_multiplier=3.0,   # ~3x more expensive than Standard
        preferred_models={
            "orchestrator": "gemini-2.5-pro",
            "coding": ["claude-opus-4", "gpt-4", "gemini-2.5-pro"],
            "testing": ["claude-3-5-sonnet"],
        },
    ),
}


class QualityTierManager:
    """Manages the active quality tier and provides model guidance to the router."""

    def __init__(self) -> None:
        self._active_tier: QualityTier = QualityTier.STANDARD

    @property
    def active_tier(self) -> QualityTier:
        return self._active_tier

    @property
    def config(self) -> TierConfig:
        return TIER_CONFIGS[self._active_tier]

    def set_tier(self, tier: QualityTier) -> None:
        self._active_tier = tier

    def cycle_tier(self) -> QualityTier:
        """Cycle through tiers: Light → Standard → Max → Light."""
        order = [QualityTier.LIGHT, QualityTier.STANDARD, QualityTier.MAX]
        current_idx = order.index(self._active_tier)
        new_idx = (current_idx + 1) % len(order)
        self._active_tier = order[new_idx]
        return self._active_tier

    def get_preferred_models(self, role: str = "coding") -> list[str]:
        return TIER_CONFIGS[self._active_tier].preferred_models.get(role, [])

    def estimate_cost_multiplier(self) -> float:
        return TIER_CONFIGS[self._active_tier].cost_multiplier
