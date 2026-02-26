"""Tests for ELO feedback loop — arbiter pushes results to EloTracker and Router."""

import inspect

import pytest

from src.core.elo_tracker import EloTracker
from src.core.router import CodingRouter


class TestEloTrackerRecordMatch:
    @pytest.fixture
    def tracker(self, tmp_path):
        db_path = str(tmp_path / "test_elo.db")
        return EloTracker(db_path=db_path)

    def test_record_match_updates_ratings(self, tracker):
        tracker.record_match(
            winner_id="openai/gpt-4o",
            loser_ids=["anthropic/claude-3-opus"],
            complexity=5,
        )
        lb = tracker.get_leaderboard()
        model_ids = [entry["id"] for entry in lb]
        assert "openai/gpt-4o" in model_ids
        assert "anthropic/claude-3-opus" in model_ids

        # Winner should have higher ELO than loser
        winner_entry = next(e for e in lb if e["id"] == "openai/gpt-4o")
        loser_entry = next(e for e in lb if e["id"] == "anthropic/claude-3-opus")
        assert winner_entry["elo_rating"] > loser_entry["elo_rating"]

    def test_record_match_with_costs(self, tracker):
        tracker.record_match(
            winner_id="a",
            loser_ids=["b"],
            costs={"a": 0.05, "b": 0.10},
        )
        lb = tracker.get_leaderboard()
        assert len(lb) == 2


class TestRouterOutcomeRecording:
    def test_record_outcome_appends(self):
        router = CodingRouter()
        router.record_outcome(
            task_id="t1",
            model_id="openai/gpt-4o",
            intent="edit",
            complexity=5,
            success=True,
        )
        assert len(router.outcomes) >= 1
        last = router.outcomes[-1]
        assert last.model_id == "openai/gpt-4o"
        assert last.success is True


class TestArbiterEloFeedback:
    def test_arbiter_contains_elo_push(self):
        """Arbiter's evaluate method must push ELO results after verdict."""
        from src.core import arbiter
        source = inspect.getsource(arbiter)
        assert "EloTracker" in source, "Arbiter does not import EloTracker"
        assert "record_match" in source, "Arbiter does not call record_match"
        assert "record_outcome" in source, "Arbiter does not call record_outcome"

    def test_router_has_elo_sort(self):
        """Router must use ELO data to re-rank candidates."""
        from src.core import router
        source = inspect.getsource(router)
        assert "_apply_elo_sort" in source, "Router missing ELO sorting"
        assert "_refresh_elo_cache" in source, "Router missing ELO cache refresh"
