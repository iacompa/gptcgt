# ruff: noqa: E501

from __future__ import annotations

from textual import on
from textual.reactive import reactive
from textual.widgets import Static

from src.core.events import AuthStateChanged, CreditsUpdated, SpendingCapWarning
from src.core.logger import get_logger

logger = get_logger("tui.status_bar")


class EnhancedStatusBar(Static):
    """
    Information-dense status bar.
    Format:
    [PLAN] 💡 Light │ Mode: Standard │ 5 cr │ Est: $0.04 │ Today: $1.42 │ Month: $18.73 │ Budget: ████████░░ 82% │ 847/1000 cr  # noqa: E501
    """

    DEFAULT_CSS = """
    EnhancedStatusBar {
        dock: bottom;
        height: 1;
        background: $panel;
        color: $text;
        content-align: center middle;
    }
    .status-warning { color: $warning; }
    .status-critical { color: $error; text-style: bold; }
    """

    tier_icon = reactive("⚡")
    tier_name = reactive("Standard")
    tier_color = reactive("$primary")

    user_plan = reactive("byok")
    is_authenticated = reactive(False)
    cap_warning = reactive("")

    op_mode = reactive("Standard")
    credits_cost = reactive(5)
    est_cost = reactive(0.04)

    running_cost = reactive(0.0)
    is_running = reactive(False)

    today_cost = reactive(0.0)
    month_cost = reactive(0.0)

    budget_pct = reactive(0.0)
    credits_remaining = reactive(1000)
    plan_credits = reactive(1000)
    is_overage = reactive(False)

    def render(self) -> str:
        # Build plan badge based on auth/plan
        plan_colors = {
            "pro": "$primary",
            "team": "$success",
            "enterprise": "#A78BFA",
            "free": "$text-muted",
            "byok": "$text-muted",
        }
        plan_color = plan_colors.get(self.user_plan, "$text-muted")
        plan_name = self.user_plan.upper()
        plan_badge = f"[{plan_color}]{plan_name}[/{plan_color}]"

        # Build tier string
        tier_str = f"[{self.tier_color}]{self.tier_icon} {self.tier_name}[/{self.tier_color}]"

        # Build mode and cost
        mode_str = f"Mode: {self.op_mode}"
        credit_str = f"{self.credits_cost} cr"

        if self.is_running:
            cost_str = f"Running: ${self.running_cost:.3f}..."
        else:
            cost_str = f"Est: ${self.est_cost:.2f}"

        # Build historical cost
        if self.user_plan.lower() == "byok":
            today_str = f"Est. Spend: ${self.today_cost:.2f}"
        else:
            today_str = f"Today: ${self.today_cost:.2f}"

        month_str = f"Month: ${self.month_cost:.2f}"

        # Build budget bar
        filled = int(self.budget_pct * 10)
        bar = ("█" * filled) + ("░" * (10 - filled))
        pct_str = f"{int(self.budget_pct * 100)}%"

        if self.is_overage:
            budget_str = f"[$error]Budget: {bar} OVERLIMIT[/$error]"
            rem_str = f"[$error]OVERAGE: +{abs(self.credits_remaining)} cr[/$error]"
        else:
            # Color shifts based on cap_warning explicitly set by backend now
            color = "$success"
            if self.cap_warning == "warning":
                color = "$warning"
            if self.cap_warning in ["critical", "blocked"]:
                color = "$error"

            warning_icon = "⚠️ " if self.cap_warning else ""
            budget_str = f"[{color}]Budget: {warning_icon}{bar} {pct_str}[/{color}]"
            rem_str = f"{self.credits_remaining}/{self.plan_credits} cr"

        parts = [
            plan_badge,
            tier_str,
            mode_str,
            credit_str,
            cost_str,
            today_str,
            month_str,
            budget_str,
            rem_str,
        ]

        return " │ ".join(parts)

    # Dispatched model display is handled by the ActiveAgentsBar component, not the global config op_mode  # noqa: E501

    @on(CreditsUpdated)
    def handle_credits_updated(self, event: CreditsUpdated) -> None:
        self.credits_remaining = event.credits_remaining
        self.plan_credits = event.credits_monthly
        try:
            import textual.app as _tapp
            current_app = _tapp.active_app.get()
            if hasattr(current_app, "cost_tracker"):
                self.today_cost = current_app.cost_tracker.get_today_spend().total_cost
                self.month_cost = current_app.cost_tracker.get_monthly_spend()
        except Exception as e:
            logger.debug(f"Status bar credits update failed: {e}")

    @on(SpendingCapWarning)
    def handle_cap_warning(self, event: SpendingCapWarning) -> None:
        self.cap_warning = event.warning_level
        self.budget_pct = event.percent_used / 100

    @on(AuthStateChanged)
    def handle_auth_changed(self, event: AuthStateChanged) -> None:
        self.is_authenticated = event.is_authenticated
        self.user_plan = event.plan if event.is_authenticated else "byok"
