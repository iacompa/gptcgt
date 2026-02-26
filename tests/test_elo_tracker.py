import os

import pytest

from src.core.elo_tracker import EloTracker


@pytest.fixture
def elo_db(tmp_path):
    db_file = tmp_path / "test_elo.db"
    tracker = EloTracker(db_path=str(db_file))
    yield tracker
    if db_file.exists():
        os.remove(db_file)

def test_elo_initialization(elo_db):
    leaderboard = elo_db.get_leaderboard()
    assert len(leaderboard) == 0

def test_record_match_and_elo_update(elo_db):
    costs = {"claude-3.5-sonnet": 0.05, "gpt-4o-mini": 0.01}
    success = elo_db.record_match(
        winner_id="claude-3.5-sonnet",
        loser_ids=["gpt-4o-mini"],
        complexity=1,
        duration_sec=10.5,
        costs=costs
    )

    assert success

    leaderboard = elo_db.get_leaderboard()
    assert len(leaderboard) == 2

    winner = next(m for m in leaderboard if m["id"] == "claude-3.5-sonnet")
    loser = next(m for m in leaderboard if m["id"] == "gpt-4o-mini")

    # ELO starts at 1200, winner should go up, loser down
    assert winner["elo_rating"] > 1200.0
    assert loser["elo_rating"] < 1200.0

    # Stats
    assert winner["matches_won"] == 1
    assert winner["matches_lost"] == 0
    assert winner["total_spent"] == 0.05
    assert winner["win_rate"] == 100.0

    assert loser["matches_won"] == 0
    assert loser["matches_lost"] == 1
    assert loser["total_spent"] == 0.01
    assert loser["win_rate"] == 0.0

def test_multiple_losers(elo_db):
    success = elo_db.record_match(
        winner_id="omni",
        loser_ids=["flash", "haiku"]
    )

    assert success
    leaderboard = elo_db.get_leaderboard()
    assert len(leaderboard) == 3

    winner = next(m for m in leaderboard if m["id"] == "omni")
    assert winner["matches_won"] == 1
    assert winner["elo_rating"] > 1200.0 # Beat two baseline models, should go up decently
