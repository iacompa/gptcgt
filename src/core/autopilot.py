"""
Phase 4 — Token/Cost Autopilot.

Rules-first autopilot that controls spend and latency automatically.

Features:
  - Per-mode budgets for lite, standard, max with hard token and dollar ceilings.
  - Simple decision policy: picks mode from task complexity + budget health + success rate.
  - Graceful downgrade ladder: max -> standard -> lite when budget/SLO pressure rises.
  - Transparent "why this mode was chosen" messages and per-run cost forecasts.

No ML-based routing yet; pure rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.core.logger import get_logger

logger = get_logger("core.autopilot")


# ── Mode tiers ──────────────────────────────────────────────────────────
class ModeTier(str, Enum):
    LITE = "lite"
    STANDARD = "standard"
    MAX = "max"


# ── Per-mode budget definition ──────────────────────────────────────────
@dataclass
class ModeBudget:
    """Hard ceilings per mode tier."""

    tier: ModeTier
    max_tokens_output: int
    max_cost_usd: float
    max_context_tokens: int

    # Estimated cost per 1K output tokens (for forecasting)
    est_cost_per_1k_output: float = 0.0


# Default budgets
DEFAULT_MODE_BUDGETS: dict[ModeTier, ModeBudget] = {
    ModeTier.LITE: ModeBudget(
        tier=ModeTier.LITE,
        max_tokens_output=2000,
        max_cost_usd=0.05,
        max_context_tokens=32_000,
        est_cost_per_1k_output=0.001,
    ),
    ModeTier.STANDARD: ModeBudget(
        tier=ModeTier.STANDARD,
        max_tokens_output=8000,
        max_cost_usd=0.50,
        max_context_tokens=100_000,
        est_cost_per_1k_output=0.010,
    ),
    ModeTier.MAX: ModeBudget(
        tier=ModeTier.MAX,
        max_tokens_output=16000,
        max_cost_usd=2.00,
        max_context_tokens=200_000,
        est_cost_per_1k_output=0.030,
    ),
}

# ── Downgrade ladder ────────────────────────────────────────────────────
DOWNGRADE_LADDER = [ModeTier.MAX, ModeTier.STANDARD, ModeTier.LITE]


# ── Decision context ────────────────────────────────────────────────────
@dataclass
class BudgetHealth:
    """Current state of budget consumption."""

    daily_spend_usd: float = 0.0
    daily_limit_usd: float = 10.0
    session_spend_usd: float = 0.0
    session_limit_usd: float = 20.0
    recent_success_rate: float = 1.0  # 0.0 - 1.0

    @property
    def daily_remaining(self) -> float:
        return max(0.0, self.daily_limit_usd - self.daily_spend_usd)

    @property
    def session_remaining(self) -> float:
        return max(0.0, self.session_limit_usd - self.session_spend_usd)

    @property
    def budget_pressure(self) -> float:
        """0.0 = no pressure, 1.0 = maxed out."""
        daily_pct = self.daily_spend_usd / max(self.daily_limit_usd, 0.01)
        session_pct = self.session_spend_usd / max(self.session_limit_usd, 0.01)
        return max(daily_pct, session_pct)


# ── Autopilot decision result ──────────────────────────────────────────
@dataclass
class AutopilotDecision:
    """Result of mode selection with full rationale."""

    selected_tier: ModeTier = ModeTier.STANDARD
    budget: ModeBudget = field(default_factory=lambda: DEFAULT_MODE_BUDGETS[ModeTier.STANDARD])
    reason: str = ""
    cost_forecast_usd: float = 0.0
    was_downgraded: bool = False
    original_tier: ModeTier | None = None

    def to_text(self) -> str:
        lines = [f"Mode: {self.selected_tier.value.upper()}"]
        if self.was_downgraded:
            lines.append(f"  ↓ Downgraded from {self.original_tier.value}")
        lines.append(f"  Reason: {self.reason}")
        lines.append(f"  Forecast: ~${self.cost_forecast_usd:.4f}")
        lines.append(f"  Token cap: {self.budget.max_tokens_output}")
        return "\n".join(lines)


# ── Autopilot engine ────────────────────────────────────────────────────
class CostAutopilot:
    """
    Rules-first autopilot for mode selection.
    Deterministic: same inputs always produce same output.
    """

    def __init__(self, budgets: dict[ModeTier, ModeBudget] | None = None) -> None:
        self.budgets = budgets or dict(DEFAULT_MODE_BUDGETS)

    def select_mode(
        self,
        complexity: int,
        budget_health: BudgetHealth,
        preferred_tier: ModeTier | None = None,
    ) -> AutopilotDecision:
        """
        Pick mode from complexity + budget health + success rate.
        Deterministic for same inputs.
        """
        # Step 1: Determine ideal tier from complexity
        if complexity <= 3:
            ideal = ModeTier.LITE
        elif complexity <= 7:
            ideal = ModeTier.STANDARD
        else:
            ideal = ModeTier.MAX

        # Allow user preference to override upward
        if preferred_tier:
            ideal_idx = DOWNGRADE_LADDER.index(ideal)
            pref_idx = DOWNGRADE_LADDER.index(preferred_tier)
            if pref_idx < ideal_idx:  # MAX < STANDARD < LITE in index
                ideal = preferred_tier

        original = ideal
        reason_parts = [f"complexity={complexity}/10 → {ideal.value}"]

        # Step 2: Check budget pressure → downgrade if needed
        pressure = budget_health.budget_pressure
        if pressure > 0.9:
            reason_parts.append(f"budget pressure {pressure:.0%} → forcing LITE")
            ideal = ModeTier.LITE
        elif pressure > 0.7 and ideal == ModeTier.MAX:
            reason_parts.append(f"budget pressure {pressure:.0%} → downgrading from MAX")
            ideal = ModeTier.STANDARD

        # Step 3: Check success rate → downgrade if recent failures
        if budget_health.recent_success_rate < 0.5 and ideal == ModeTier.MAX:
            reason_parts.append(f"success rate {budget_health.recent_success_rate:.0%} → downgrading")
            ideal = ModeTier.STANDARD

        # Step 4: Verify chosen tier fits remaining budget
        budget = self.budgets[ideal]
        forecast = budget.est_cost_per_1k_output * (budget.max_tokens_output / 1000)

        if forecast > budget_health.daily_remaining:
            # Walk down the ladder
            for tier in DOWNGRADE_LADDER:
                tier_idx = DOWNGRADE_LADDER.index(tier)
                if tier_idx >= DOWNGRADE_LADDER.index(ideal):
                    b = self.budgets[tier]
                    f = b.est_cost_per_1k_output * (b.max_tokens_output / 1000)
                    if f <= budget_health.daily_remaining:
                        ideal = tier
                        budget = b
                        forecast = f
                        reason_parts.append(f"forecast ${forecast:.4f} > remaining → {tier.value}")
                        break

        was_downgraded = ideal != original

        return AutopilotDecision(
            selected_tier=ideal,
            budget=budget,
            reason="; ".join(reason_parts),
            cost_forecast_usd=forecast,
            was_downgraded=was_downgraded,
            original_tier=original if was_downgraded else None,
        )

    def enforce_cap(self, tier: ModeTier, actual_cost: float) -> tuple[bool, str]:
        """Check if actual cost exceeds the hard cap for the tier. Fail-closed."""
        budget = self.budgets.get(tier, self.budgets[ModeTier.STANDARD])
        if actual_cost > budget.max_cost_usd:
            return False, f"Cost ${actual_cost:.4f} exceeds {tier.value} cap of ${budget.max_cost_usd:.2f}"
        return True, "within budget"
