import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.logger import get_logger

log = get_logger(__name__)

class EloTracker:
    """
    Tracks ELO ratings, match histories, and financial costs for LLM models
    competing inside the GPTCGT Arena.
    """
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Default to tracking inside the user's gptcgt config folder
            home_dir = Path.home() / ".gptcgt"
            home_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(home_dir / "elo.db")
        else:
            self.db_path = db_path

        self._init_db()

    def _init_db(self):
        """Initialize the SQLite schema if it doesn't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Models table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS models (
                        id TEXT PRIMARY KEY,
                        elo_rating REAL DEFAULT 1200.0,
                        matches_won INTEGER DEFAULT 0,
                        matches_lost INTEGER DEFAULT 0,
                        total_spent REAL DEFAULT 0.0
                    )
                """)

                # Matches tracking table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS matches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL,
                        winning_model TEXT,
                        complexity INTEGER,
                        duration_sec REAL,
                        cost REAL,
                        FOREIGN KEY(winning_model) REFERENCES models(id)
                    )
                """)

                # Match participants (since multiple models can lose a single match)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS match_participants (
                        match_id INTEGER,
                        model_id TEXT,
                        is_winner BOOLEAN,
                        cost REAL,
                        FOREIGN KEY(match_id) REFERENCES matches(id),
                        FOREIGN KEY(model_id) REFERENCES models(id),
                        PRIMARY KEY (match_id, model_id)
                    )
                """)

                conn.commit()
        except sqlite3.Error as e:
            log.error(f"Failed to initialize EloTracker database: {e}")

    def _ensure_model_exists(self, cursor: sqlite3.Cursor, model_id: str):
        """Ensures a model exists in the database before updating it."""
        cursor.execute("SELECT id FROM models WHERE id = ?", (model_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO models (id) VALUES (?)", (model_id,))

    def _calculate_elo(self, winner_elo: float, loser_elo: float, k_factor: float = 32.0) -> tuple[float, float]:
        """Calculates new ELO ratings for a 1v1 match."""
        # Expected win probability for winner
        expected_winner = 1.0 / (1.0 + 10.0 ** ((loser_elo - winner_elo) / 400.0))
        # Expected win probability for loser
        expected_loser = 1.0 / (1.0 + 10.0 ** ((winner_elo - loser_elo) / 400.0))

        # New ratings
        new_winner_elo = winner_elo + k_factor * (1.0 - expected_winner)
        new_loser_elo = loser_elo + k_factor * (0.0 - expected_loser)

        return new_winner_elo, new_loser_elo

    def record_match(
        self,
        winner_id: str,
        loser_ids: List[str],
        complexity: int = 1,
        duration_sec: float = 0.0,
        costs: Dict[str, float] = None
    ) -> bool:
        """
        Records an arena match outcome and updates ELO ratings.
        costs should be a dictionary mapping model_id to the cost incurred in this match.
        """
        if not costs:
            costs = {}

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 1. Ensure all models exist
                self._ensure_model_exists(cursor, winner_id)
                for loser_id in loser_ids:
                    self._ensure_model_exists(cursor, loser_id)

                # 2. Record the match
                winner_cost = costs.get(winner_id, 0.0)
                cursor.execute("""
                    INSERT INTO matches (timestamp, winning_model, complexity, duration_sec, cost)
                    VALUES (?, ?, ?, ?, ?)
                """, (time.time(), winner_id, complexity, duration_sec, winner_cost))
                match_id = cursor.lastrowid

                # 3. Record participants and total spend
                # Winner
                cursor.execute("""
                    INSERT INTO match_participants (match_id, model_id, is_winner, cost)
                    VALUES (?, ?, ?, ?)
                """, (match_id, winner_id, True, winner_cost))

                cursor.execute("""
                    UPDATE models SET matches_won = matches_won + 1, total_spent = total_spent + ?
                    WHERE id = ?
                """, (winner_cost, winner_id))

                # Losers
                for loser_id in loser_ids:
                    loser_cost = costs.get(loser_id, 0.0)
                    cursor.execute("""
                        INSERT INTO match_participants (match_id, model_id, is_winner, cost)
                        VALUES (?, ?, ?, ?)
                    """, (match_id, loser_id, False, loser_cost))

                    cursor.execute("""
                        UPDATE models SET matches_lost = matches_lost + 1, total_spent = total_spent + ?
                        WHERE id = ?
                    """, (loser_cost, loser_id))

                # 4. Calculate and update ELO
                cursor.execute("SELECT elo_rating FROM models WHERE id = ?", (winner_id,))
                winner_elo = cursor.fetchone()[0]

                # For multiple losers, process as individual 1v1 matches against the winner
                for loser_id in loser_ids:
                    cursor.execute("SELECT elo_rating FROM models WHERE id = ?", (loser_id,))
                    loser_elo = cursor.fetchone()[0]

                    # Calculate new ELOs
                    new_winner_elo, new_loser_elo = self._calculate_elo(winner_elo, loser_elo)

                    # Update loser ELO immediately
                    cursor.execute("UPDATE models SET elo_rating = ? WHERE id = ?", (new_loser_elo, loser_id))

                    # Prepare winner ELO for next iteration (or final update)
                    winner_elo = new_winner_elo

                # Final winner ELO update
                cursor.execute("UPDATE models SET elo_rating = ? WHERE id = ?", (winner_elo, winner_id))

                conn.commit()
                return True

        except sqlite3.Error as e:
            log.error(f"Failed to record match in EloTracker: {e}")
            return False

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """
        Retrieves the current ELO leaderboard.
        Returns a list of dictionaries sorted by ELO rating descending.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT 
                        id, 
                        elo_rating, 
                        matches_won, 
                        matches_lost, 
                        total_spent,
                        (matches_won + matches_lost) as total_matches,
                        CASE 
                            WHEN (matches_won + matches_lost) > 0 THEN 
                                ROUND(CAST(matches_won AS FLOAT) / (matches_won + matches_lost) * 100, 1)
                            ELSE 0.0
                        END as win_rate
                    FROM models
                    ORDER BY elo_rating DESC, matches_won DESC
                """)

                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            log.error(f"Failed to fetch leaderboard: {e}")
            return []
