from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Static

from src.core.elo_tracker import EloTracker


class LeaderboardPanel(Vertical):
    """
    Displays the Local Gamified ELO Leaderboard tracking arena matchups
    within the target codebase.
    """

    DEFAULT_CSS = """
    LeaderboardPanel {
        layer: overlay;
        position: absolute;
        width: 100%;
        height: 100%;
        padding: 1;
        background: $surface;
        border: solid $primary;
        display: none;
    }


    LeaderboardPanel.visible {
        display: block;
    }

    LeaderboardPanel > Static#leaderboard-title {
        content-align: center middle;
        text-style: bold;
        color: $text;
        height: 3;
        background: $primary 15%;
        margin-bottom: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tracker = EloTracker()

    def compose(self) -> ComposeResult:
        yield Static("🏆 GPTCGT Local Arena Leaderboard 🏆", id="leaderboard-title")
        yield DataTable(id="elo-table", zebra_stripes=True)

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Rank", "Model", "ELO Rating", "Win Rate", "Matches", "Total Cost")
        self.refresh_data()

    def refresh_data(self) -> None:
        """Fetch fresh match data and re-render the rows."""
        table = self.query_one(DataTable)
        table.clear()

        leaders = self.tracker.get_leaderboard()
        for i, row in enumerate(leaders):
            # Format row strings for neat display
            table.add_row(
                f"#{i + 1}",
                row["id"],
                f"{row['elo_rating']:.1f}",
                f"{row['win_rate']}%",
                f"{row['total_matches']}",
                f"${row['total_spent']:.4f}",
            )

    def toggle_visibility(self) -> None:
        """Toggles the panel view and reloads memory organically."""
        if self.has_class("visible"):
            self.remove_class("visible")
        else:
            self.refresh_data()
            self.add_class("visible")
            self.query_one(DataTable).focus()
