from textual.app import ComposeResult
from textual.widgets import Static
from textual.reactive import reactive

class EnhancedStatusBar(Static):
    """
    Information-dense status bar.
    Format:
    💡 Light │ Mode: Standard │ 5 cr │ Est: $0.04 │ Today: $1.42 │ Month: $18.73 │ Budget: ████████░░ 82% │ 847/1000 cr
    """
    
    DEFAULT_CSS = """
    EnhancedStatusBar {
        dock: bottom;
        height: 1;
        background: #161B22;
        color: #E6EDF3;
        content-align: center middle;
    }
    .status-warning { color: #D29922; }
    .status-critical { color: #F85149; text-style: bold; }
    """

    tier_icon = reactive("⚡")
    tier_name = reactive("Standard")
    tier_color = reactive("#58A6FF")
    
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
        # Build tier string
        tier_str = f"[{self.tier_color}]{self.tier_icon} {self.tier_name}[/]"
        
        # Build mode and cost
        mode_str = f"Mode: {self.op_mode}"
        credit_str = f"{self.credits_cost} cr"
        
        if self.is_running:
            cost_str = f"Running: ${self.running_cost:.3f}..."
        else:
            cost_str = f"Est: ${self.est_cost:.2f}"
            
        # Build historical cost
        today_str = f"Today: ${self.today_cost:.2f}"
        month_str = f"Month: ${self.month_cost:.2f}"
        
        # Build budget bar
        filled = int(self.budget_pct * 10)
        bar = ("█" * filled) + ("░" * (10 - filled))
        pct_str = f"{int(self.budget_pct * 100)}%"
        
        if self.is_overage:
            budget_str = f"[#F85149]Budget: {bar} OVERLIMIT[/]"
            rem_str = f"[#F85149]OVERAGE: +{abs(self.credits_remaining)} cr[/]"
        else:
            color = "#3FB950" if self.budget_pct < 0.8 else ("#D29922" if self.budget_pct < 0.95 else "#F85149")
            budget_str = f"[{color}]Budget: {bar} {pct_str}[/]"
            rem_str = f"{self.credits_remaining}/{self.plan_credits} cr"

        parts = [
            tier_str,
            mode_str,
            credit_str,
            cost_str,
            today_str,
            month_str,
            budget_str,
            rem_str
        ]
        
        return " │ ".join(parts)
