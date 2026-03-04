"""
Unified credit cost computation.

Single source of truth for calculating credit cost from tokens and model.
Used by both api/routes/proxy.py and proxy/metering.py.
"""

from __future__ import annotations

from src.core.logger import get_logger

logger = get_logger("services.cost_computation")

# Cost multipliers per-model tier (credits per 1K tokens)
# These should be kept in sync with pricing page
MODEL_COST_TABLE: dict[str, float] = {
    # Scout tier — cheap/fast models
    "scout": 0.1,
    # Standard tier — mid-range models
    "standard": 0.5,
    # Architect tier — premium reasoning models
    "architect": 2.0,
    # Ensemble tier — multi-model runs
    "ensemble": 1.5,
    # Sandbox — fixed cost
    "sandbox": 1.0,
}

# Model name → tier mapping (substring match)
_MODEL_TIER_KEYWORDS: dict[str, str] = {
    "haiku": "scout",
    "flash": "scout",
    "mini": "scout",
    "nano": "scout",
    "small": "scout",
    "lite": "scout",
    "sonnet": "standard",
    "gpt-4o": "standard",
    "pro": "standard",
    "gemini-2": "standard",
    "opus": "architect",
    "o1": "architect",
    "o3": "architect",
    "reasoning": "architect",
    "ensemble": "ensemble",
}


def determine_tier(model: str) -> str:
    """Determine the billing tier for a model name."""
    if not model:
        return "standard"
    model_lower = model.lower()
    for keyword, tier in _MODEL_TIER_KEYWORDS.items():
        if keyword in model_lower:
            return tier
    return "standard"


def compute_credit_cost(
    tokens_used: int | None = None,
    model: str = "unknown",
    mode: str | None = None,
) -> int:
    """
    Compute the credit cost for a request.

    Args:
        tokens_used: Total tokens (input + output). If None, uses minimum 1 credit.
        model: Model name string for tier determination.
        mode: Optional explicit mode override (bypasses model-based detection).

    Returns:
        Credits to deduct (integer, minimum 1).

    """
    tier = mode if mode and mode in MODEL_COST_TABLE else determine_tier(model)
    rate = MODEL_COST_TABLE.get(tier, 0.5)  # credits per 1K tokens

    if tokens_used is None or tokens_used <= 0:
        # Minimum 1 credit for any request
        return 1

    # Round up to ensure we never under-charge
    cost = max(1, int((tokens_used / 1000.0) * rate + 0.5))

    logger.debug(
        f"Cost computation: model={model}, tier={tier}, "
        f"tokens={tokens_used}, rate={rate}/1K, cost={cost}"
    )
    return cost
