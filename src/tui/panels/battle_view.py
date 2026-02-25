"""
Battle Mode UI components.

Extends the standard multi-agent chat view with battle-specific
visuals, like a VS screen, live scoreboards, and dramatic reveals.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, Static

from src.core.arbiter import ArbiterScore


class BattleScoreboard(Static):
    """
    Live scoreboard shown during Battle Mode.
    Displays metrics like Tokens/Sec, Total Cost, and Current Phase
    for the two competing models.
    """

    DEFAULT_CSS = """
    BattleScoreboard {
        width: 100%;
        height: auto;
        min-height: 5;
        border: solid #D2A8FF;
        background: $surface;
        margin: 1 0;
        padding: 0 1;
    }
    .bs-header {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    .bs-model-col {
        width: 1fr;
        height: auto;
    }
    .bs-vs {
        width: 5;
        text-align: center;
        color: #D2A8FF;
        text-style: bold;
    }
    .right-aligned {
        text-align: right;
    }
    """

    def __init__(self, model_a: str, emoji_a: str, model_b: str, emoji_b: str, **kwargs):
        super().__init__(**kwargs)
        self.model_a = model_a
        self.emoji_a = emoji_a
        self.model_b = model_b
        self.emoji_b = emoji_b

        self.lbl_a_status: Label | None = None
        self.lbl_b_status: Label | None = None

    def compose(self) -> ComposeResult:
        yield Label("⚔️  BATTLE MODE  ⚔️", classes="bs-header")

        with Horizontal():
            with Vertical(classes="bs-model-col"):
                yield Label(f"[{self.emoji_a}] {self.model_a}")
                self.lbl_a_status = Label("Status: Generating...")
                yield self.lbl_a_status

            yield Label("VS", classes="bs-vs")

            with Vertical(classes="bs-model-col"):
                yield Label(f"[{self.emoji_b}] {self.model_b}", classes="right-aligned")
                self.lbl_b_status = Label("Status: Generating...", classes="right-aligned")
                yield self.lbl_b_status

    def update_status(self, agent_id: str, is_p1: bool, status: str) -> None:
        """Update the live status of one of the combatants."""
        if is_p1 and self.lbl_a_status:
            self.lbl_a_status.update(f"Status: {status}")
        elif not is_p1 and self.lbl_b_status:
            self.lbl_b_status.update(f"Status: {status}")


class BattleVerdictView(Static):
    """Dramatic reveal of the Arbiter's verdict after a battle."""

    DEFAULT_CSS = """
    BattleVerdictView {
        width: 100%;
        height: auto;
        border: double #4ADE80;
        background: #031A0B;
        margin: 1 0;
        padding: 1 2;
    }
    .bv-title {
        text-align: center;
        text-style: bold;
        color: #4ADE80;
        margin-bottom: 1;
    }
    .bv-winner {
        text-align: center;
        text-style: bold italic;
        color: white;
    }
    .bv-score {
        text-align: center;
        color: $primary;
        margin-bottom: 1;
    }
    .center-aligned {
        text-align: center;
    }
    """

    def __init__(self, winner: ArbiterScore, loser: ArbiterScore | None, summary: str, **kwargs):
        super().__init__(**kwargs)
        self.winner = winner
        self.loser = loser
        self.summary = summary

    def compose(self) -> ComposeResult:
        yield Label("🏆 BATTLE CONCLUSION", classes="bv-title")
        yield Label(f"WINNER: {self.winner.model_name}", classes="bv-winner")
        yield Label(f"Score: {self.winner.total_score:.0f}/100", classes="bv-score")

        if self.loser:
            yield Label(
                f"Defeated: {self.loser.model_name} ({self.loser.total_score:.0f}/100)",
                classes="center-aligned",
            )

        yield Label(f"\n{self.summary}", classes="center-aligned")
