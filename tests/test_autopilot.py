"""Tests for Phase 4: Token/Cost Autopilot."""



def test_autopilot_selects_lite_for_low_complexity():
    """Complexity 1-3 → LITE tier."""
    from src.core.autopilot import BudgetHealth, CostAutopilot, ModeTier

    autopilot = CostAutopilot()
    budget = BudgetHealth()
    decision = autopilot.select_mode(complexity=2, budget_health=budget)

    assert decision.selected_tier == ModeTier.LITE


def test_autopilot_selects_standard_for_medium_complexity():
    """Complexity 4-7 → STANDARD tier."""
    from src.core.autopilot import BudgetHealth, CostAutopilot, ModeTier

    autopilot = CostAutopilot()
    budget = BudgetHealth()
    decision = autopilot.select_mode(complexity=5, budget_health=budget)

    assert decision.selected_tier == ModeTier.STANDARD


def test_autopilot_selects_max_for_high_complexity():
    """Complexity 8-10 → MAX tier."""
    from src.core.autopilot import BudgetHealth, CostAutopilot, ModeTier

    autopilot = CostAutopilot()
    budget = BudgetHealth()
    decision = autopilot.select_mode(complexity=9, budget_health=budget)

    assert decision.selected_tier == ModeTier.MAX


def test_autopilot_downgrades_under_budget_pressure():
    """High budget pressure (> 90%) forces LITE."""
    from src.core.autopilot import BudgetHealth, CostAutopilot, ModeTier

    autopilot = CostAutopilot()
    budget = BudgetHealth(daily_spend_usd=9.5, daily_limit_usd=10.0)
    decision = autopilot.select_mode(complexity=9, budget_health=budget)

    assert decision.selected_tier == ModeTier.LITE
    assert decision.was_downgraded is True
    assert decision.original_tier == ModeTier.MAX


def test_autopilot_moderate_pressure_downgrades_from_max():
    """70-90% budget pressure → MAX downgraded to STANDARD."""
    from src.core.autopilot import BudgetHealth, CostAutopilot, ModeTier

    autopilot = CostAutopilot()
    budget = BudgetHealth(daily_spend_usd=7.5, daily_limit_usd=10.0)
    decision = autopilot.select_mode(complexity=9, budget_health=budget)

    assert decision.selected_tier == ModeTier.STANDARD
    assert decision.was_downgraded is True


def test_autopilot_cost_forecast():
    """Decision includes a cost forecast."""
    from src.core.autopilot import BudgetHealth, CostAutopilot

    autopilot = CostAutopilot()
    budget = BudgetHealth()
    decision = autopilot.select_mode(complexity=5, budget_health=budget)

    assert decision.cost_forecast_usd > 0
    assert "Forecast" in decision.to_text()


def test_autopilot_enforce_cap_within_budget():
    """Actual cost within cap → allowed."""
    from src.core.autopilot import CostAutopilot, ModeTier

    autopilot = CostAutopilot()
    ok, msg = autopilot.enforce_cap(ModeTier.STANDARD, 0.10)
    assert ok is True


def test_autopilot_enforce_cap_exceeded():
    """Actual cost exceeds cap → blocked."""
    from src.core.autopilot import CostAutopilot, ModeTier

    autopilot = CostAutopilot()
    ok, msg = autopilot.enforce_cap(ModeTier.LITE, 1.00)
    assert ok is False
    assert "exceeds" in msg


def test_autopilot_deterministic():
    """Same inputs always produce same outputs."""
    from src.core.autopilot import BudgetHealth, CostAutopilot

    autopilot = CostAutopilot()
    budget = BudgetHealth(daily_spend_usd=3.0, daily_limit_usd=10.0)

    d1 = autopilot.select_mode(complexity=6, budget_health=budget)
    d2 = autopilot.select_mode(complexity=6, budget_health=budget)

    assert d1.selected_tier == d2.selected_tier
    assert d1.reason == d2.reason
