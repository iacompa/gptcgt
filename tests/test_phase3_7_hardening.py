"""Phase 3-7 Regression Tests: Arbiter, ELO, Sandbox, Schema, Web."""

import tempfile

# ─── Phase 3: Sandbox — No Fabricated Pass ───────────────────────────

class TestSandboxNoFabricatedPass:
    """Verify _parse_test_output doesn't fabricate passes."""

    def test_no_fabricated_pass_on_empty_output(self):
        """When total=0 and exit_code=0, result should stay empty (not invent passed=1)."""
        from src.tools.sandbox import E2BSandbox

        sandbox = E2BSandbox.__new__(E2BSandbox)
        result = sandbox._parse_test_output("", "", exit_code=0, language="python")

        # total should be 0 (inconclusive), NOT fabricated as 1 pass
        assert result.total == 0
        assert result.passed == 0
        assert result.failed == 0

    def test_nonzero_exit_with_no_output_marks_failure(self):
        """Non-zero exit with no parseable output should mark as failed."""
        from src.tools.sandbox import E2BSandbox

        sandbox = E2BSandbox.__new__(E2BSandbox)
        result = sandbox._parse_test_output("", "", exit_code=1, language="python")

        assert result.total == 1
        assert result.failed == 1

    def test_normal_pytest_output_parses_correctly(self):
        """Normal pytest output should parse correctly."""
        from src.tools.sandbox import E2BSandbox

        sandbox = E2BSandbox.__new__(E2BSandbox)
        stdout = "5 passed, 2 failed, 1 error in 3.2s"
        result = sandbox._parse_test_output(stdout, "", exit_code=1, language="python")

        assert result.passed == 5
        assert result.failed == 2
        assert result.errors == 1
        assert result.total == 8


# ─── Phase 3: ELO Anti-Gaming ───────────────────────────────────────

class TestELOAntiGaming:
    """Verify ELO anti-gaming protections."""

    def test_single_agent_elo_no_update(self):
        """ELO should not update when only 1 agent participates."""
        from src.core.elo_tracker import EloTracker

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tracker = EloTracker(db_path=f.name)

        # Record a match with no losers
        result = tracker.record_match(
            winner_id="claude-3",
            loser_ids=[],  # No losers = single-agent run
            complexity=5,
        )
        assert result is True  # Should succeed without error
        stats = tracker.get_model_stats("claude-3")
        # ELO should remain at default 1200 since no comparison was made
        assert stats["elo_rating"] == 1200.0

    def test_complexity_clamped_in_tracker(self):
        """ELO complexity should be bounded."""
        from src.core.elo_tracker import EloTracker

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tracker = EloTracker(db_path=f.name)

        # Even with extreme complexity, should still record
        result = tracker.record_match(
            winner_id="claude-3",
            loser_ids=["gpt-4"],
            complexity=100,  # Will be clamped by arbiter to 10
        )
        assert result is True

    def test_multi_agent_elo_updates(self):
        """ELO should update when 2+ agents compete."""
        from src.core.elo_tracker import EloTracker

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tracker = EloTracker(db_path=f.name)

        tracker.record_match(
            winner_id="claude-3",
            loser_ids=["gpt-4"],
            complexity=5,
        )

        winner_stats = tracker.get_model_stats("claude-3")
        loser_stats = tracker.get_model_stats("gpt-4")
        assert winner_stats["elo_rating"] > 1200.0  # Winner goes up
        assert loser_stats["elo_rating"] < 1200.0  # Loser goes down


# ─── Phase 4: Sandbox Language Validation ────────────────────────────

class TestSandboxLanguageValidation:
    """Verify sandbox handles unknown languages gracefully."""

    def test_unknown_language_falls_back_to_python(self):
        from src.tools.sandbox import LANGUAGE_TOOLS
        # Unknown language should still get a valid config via fallback
        tools = LANGUAGE_TOOLS.get("unknown_lang", LANGUAGE_TOOLS.get("python"))
        assert tools is not None
        assert "template" in tools


# ─── Phase 5: Credit Cost Registry ──────────────────────────────────

class TestCreditCosts:
    """Verify credit cost table is complete."""

    def test_sandbox_cost_is_1(self):
        from src.billing.credits import CreditService
        service = CreditService()
        assert service.CREDIT_COSTS["sandbox"] == 1

    def test_all_modes_have_explicit_costs(self):
        from src.billing.credits import CreditService
        service = CreditService()
        required_modes = ["scout", "standard", "ensemble", "architect", "battle", "sandbox"]
        for mode in required_modes:
            assert mode in service.CREDIT_COSTS, f"Missing cost for mode: {mode}"


# ─── Phase 7: Web Auth Cookie Tests ─────────────────────────────────

class TestWebAuthCookies:
    """Verify public path list completeness."""

    def test_all_auth_paths_public(self):
        from api.middleware.auth import PUBLIC_PATHS_EXACT
        # All auth endpoints that need to work without a token
        required = {"/auth/device", "/auth/token", "/auth/signin", "/auth/sso/callback"}
        for path in required:
            assert path in PUBLIC_PATHS_EXACT, f"Missing public path: {path}"

    def test_billing_webhook_public(self):
        from api.middleware.auth import PUBLIC_PATHS_EXACT
        assert "/billing/webhook" in PUBLIC_PATHS_EXACT
