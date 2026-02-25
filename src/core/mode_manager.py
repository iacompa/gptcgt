"""
Operation mode manager. Handles the transition between Scout (cheap analysis)
and Standard (heavy execution), and checks user credit limits to auto-downgrade
if necessary.
"""

from __future__ import annotations

from enum import Enum

from src.core.logger import get_logger
from src.core.quality_tiers import QualityTier

logger = get_logger("core.mode_manager")


class OperationMode(Enum):
    SCOUT = "scout"  # Analysis, fast, cheap
    STANDARD = "standard"  # Execution, smart, expensive
    ENSEMBLE = "ensemble"  # Parallel generation (2-3 models)
    ARCHITECT = "architect"  # Parallel planning -> single coder
    BATTLE = "battle"  # Competitive generation (2 models)
    SINGLE_MODEL_OPENAI = "single_model_openai"
    SINGLE_MODEL_ANTHROPIC = "single_model_anthropic"
    SINGLE_MODEL_GOOGLE = "single_model_google"
    SINGLE_MODEL_DEEPSEEK = "single_model_deepseek"


CREDIT_COSTS = {
    OperationMode.SCOUT: 1,
    OperationMode.STANDARD: 5,
    OperationMode.ENSEMBLE: 25,
    OperationMode.ARCHITECT: 100,
    OperationMode.BATTLE: 25,
    OperationMode.SINGLE_MODEL_OPENAI: 5,
    OperationMode.SINGLE_MODEL_ANTHROPIC: 5,
    OperationMode.SINGLE_MODEL_GOOGLE: 5,
    OperationMode.SINGLE_MODEL_DEEPSEEK: 5,
}


class ModeManager:
    def __init__(self):
        self.active_mode = OperationMode.STANDARD
        self.current_credits_used = 0

    def check_credits(self, mode: OperationMode) -> bool:
        """Check if we have enough simulated credits for the mode."""
        cost = CREDIT_COSTS.get(mode, 5)
        try:
            import textual.app as _tapp
            current_app = _tapp.active_app.get()
            if hasattr(current_app, "auth_manager") and getattr(
                current_app.auth_manager, "use_managed_credits", False
            ):
                if getattr(current_app.auth_manager, "credits_remaining", 0) < cost:
                    return False
        except Exception:
            pass
        return True

    def set_mode(self, mode: OperationMode) -> None:
        """Explicitly override the operating mode."""
        self.active_mode = mode
        logger.info(f"Operation mode explicitly set to: {mode.name}")

    def initialize_task(self, _requested_tier: QualityTier) -> None:
        """Sets up the mode for a new task. Checks budget constraints.
        
        IMPORTANT: Only applies the STANDARD fallback if the mode was not
        already explicitly set by the user (e.g., ENSEMBLE, BATTLE, ARCHITECT).
        This prevents every task dispatch from silently overriding the user's
        UI choice back to STANDARD.
        """
        try:
            import textual.app as _tapp
            current_app = _tapp.active_app.get()
            if hasattr(current_app, "cost_tracker"):
                today_spend = current_app.cost_tracker.get_today_spend()
                # Assuming a naive daily limit is $5.00 for simulation purposes
                daily_limit = 5.00
                if today_spend.total_cost >= daily_limit * 0.9:
                    logger.warning(
                        f"Approaching daily limit (${today_spend.total_cost:.2f}/${daily_limit:.2f}), forcing SCOUT mode."  # noqa: E501
                    )
                    self.active_mode = OperationMode.SCOUT
                    return
        except Exception as e:
            logger.debug(f"Could not access cost tracker: {e}")

        # Only fall back to STANDARD if the mode was not explicitly chosen by the user.
        # ARCHITECT, ENSEMBLE, BATTLE, and SINGLE_MODEL_* modes must be preserved.
        _preserved_modes = {
            OperationMode.ENSEMBLE,
            OperationMode.ARCHITECT,
            OperationMode.BATTLE,
            OperationMode.SINGLE_MODEL_OPENAI,
            OperationMode.SINGLE_MODEL_ANTHROPIC,
            OperationMode.SINGLE_MODEL_GOOGLE,
            OperationMode.SINGLE_MODEL_DEEPSEEK,
        }
        if self.active_mode not in _preserved_modes:
            self.active_mode = OperationMode.STANDARD

    def track_credits_used(self, credits: int) -> None:
        self.current_credits_used += credits
