from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OverageState:
    plan_credits: int
    used_credits: int
    remaining_credits: int
    is_in_overage: bool
    overage_credits: int
    overage_cost: float
    overage_enabled: bool
    auto_downgrade: bool


class OverageManager:
    def __init__(self) -> None:
        # Defaults for now
        self.state = OverageState(
            plan_credits=1000,
            used_credits=0,
            remaining_credits=1000,
            is_in_overage=False,
            overage_credits=0,
            overage_cost=0.0,
            overage_enabled=False,
            auto_downgrade=True,
        )

    def check_can_proceed(self, credits_needed: int) -> dict:
        remaining = self.state.remaining_credits

        if remaining >= credits_needed:
            return {"can_proceed": True, "reason": "ok", "action": "proceed", "message": ""}

        if remaining < credits_needed and remaining > 0:
            return {
                "can_proceed": self.state.overage_enabled,
                "reason": "low_credits",
                "action": "warn" if self.state.overage_enabled else "block",
                "message": f"You have {remaining} credits left. This task needs {credits_needed}. Enable overage in Settings to continue.",  # noqa: E501
            }

        # remaining <= 0 case
        if self.state.overage_enabled:
            return {
                "can_proceed": True,
                "reason": "overage_active",
                "action": "proceed",
                "message": "Using overage credits.",
            }

        if self.state.auto_downgrade:
            return {
                "can_proceed": True,
                "reason": "overage_disabled",
                "action": "downgrade",
                "message": "Credits exhausted. Auto-switched to Light tier / Scout mode.",
            }

        return {
            "can_proceed": False,
            "reason": "no_credits",
            "action": "block",
            "message": "Monthly credits exhausted. Enable overage billing in Settings or wait for renewal.",  # noqa: E501
        }

    def record_overage_usage(self, credits: int) -> None:
        self.state.used_credits += credits
        self.state.remaining_credits -= credits
        if self.state.remaining_credits < 0:
            self.state.is_in_overage = True
            self.state.overage_credits = abs(self.state.remaining_credits)
            self.state.overage_cost = self.state.overage_credits * 0.025

    def get_overage_warning_message(self) -> str | None:
        pct_used = self.state.used_credits / max(1, self.state.plan_credits)
        if pct_used >= 1.0:
            return "Monthly credits exhausted" + (" (Overage Active)" if self.state.overage_enabled else " (Blocked)")
        if pct_used >= 0.95:
            return f"⚠️ {self.state.remaining_credits} credits remaining. Consider enabling overage billing."  # noqa: E501
        if pct_used >= 0.80:
            return f"You've used {self.state.used_credits} of {self.state.plan_credits} credits this month."  # noqa: E501
        return None
