"""
Interactive Arbiter Verdict Panel.
Displays the evaluation metrics from an ArbiterVerdict in a structured,
clickable format instead of a plain text dump.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Collapsible, Label

from src.core.arbiter import ArbiterVerdict
from src.core.diff_engine import MultiAgentPatchSet
from src.core.events import PatchSetProposed
from src.core.logger import get_logger

logger = get_logger("tui.arbiter_verdict_panel")


class ArbiterVerdictPanel(Vertical):
    """
    Renders an ArbiterVerdict with nested metrics and reasoning.
    Provides buttons to quickly view the winning patch or individual agent patches.
    """

    DEFAULT_CSS = """
    ArbiterVerdictPanel {
        width: 100%;
        height: auto;
        background: $background;
        border: solid $secondary;
        padding: 1 2;
        margin: 1 0;
    }
    .av-header {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }
    .av-winner {
        color: $primary;
        text-style: bold;
    }
    .av-score-container {
        margin: 1 0;
        padding: 0 1;
        border-left: solid $secondary;
    }
    .av-score-agent {
        color: $warning;
        text-style: bold;
    }
    .av-stat {
        color: $text-muted;
    }
    """

    def __init__(self, verdict: ArbiterVerdict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.verdict = verdict

    @staticmethod
    def _score_bar(value: float, width: int = 10) -> str:
        """Render a visual progress bar: value 0-100 → e.g. `████████░░ 82`."""
        filled = max(0, min(width, int(round(value / 100 * width))))
        bar = "█" * filled + "░" * (width - filled)
        return f"{bar} {int(value):3d}"

    def compose(self) -> ComposeResult:
        winner = self.verdict.winner
        yield Label("🎯 [bold]Arbiter Decision[/bold]", classes="av-header")

        # Check if all agents were eliminated
        non_eliminated = [s for s in self.verdict.scores if not s.eliminated]
        if not non_eliminated:
            yield Label("[red]All patches rejected.[/red]")
        elif winner:
            yield Label(
                f"Winner: [bold]{winner.agent_id}[/bold] ({winner.model_name}) — "
                f"Score: {winner.total_score:.1f} — Confidence: {self.verdict.confidence}",
                classes="av-winner",
            )

        yield Label(f"\n[italic]{self.verdict.comparison_summary}[/italic]\n")

        with Collapsible(title="View Score Breakdown", collapsed=True):
            for score in self.verdict.scores:
                with Vertical(classes="av-score-container"):
                    status = "[red]Eliminated[/red]" if score.eliminated else "[green]Valid[/green]"
                    yield Label(
                        f"Agent {score.agent_id} ({score.model_name}) — {status}",
                        classes="av-score-agent",
                    )
                    total_bar = self._score_bar(score.total_score)
                    yield Label(f"Total: {total_bar}", classes="av-stat")

                    # Per-dimension bars
                    ss = score.stage_scores
                    dims = [
                        ("Structural", "structural_validity"),
                        ("Lint      ", "lint_cleanliness"),
                        ("Tests     ", "test_pass_rate"),
                        ("Security  ", "security_score"),
                        ("Diff      ", "diff_minimality"),
                        ("Complexity", "complexity_delta"),
                    ]
                    for label_str, key in dims:
                        v = ss.get(key, 0)
                        bar = self._score_bar(v, width=8)
                        color = "$success" if v >= 70 else ("$warning" if v >= 40 else "$error")
                        yield Label(
                            f"  [{color}]{label_str}[/{color}]: {bar}",
                            classes="av-stat",
                        )

                    if score.eliminated and score.elimination_reason:
                        yield Label(
                            f"[red]Reason: {score.elimination_reason}[/red]", classes="av-stat"
                        )

                    if score.patch_set and not score.eliminated:
                        btn = Button(
                            "View Patch", id=f"btn-patch-{score.agent_id}", variant="primary"
                        )
                        btn._patch_set = score.patch_set
                        yield btn
                    elif score.patch_set and score.eliminated:
                        # Allow viewing even eliminated patches for comparison
                        btn = Button(
                            "View Rejected Patch", id=f"btn-patch-{score.agent_id}", variant="default"
                        )
                        btn._patch_set = score.patch_set
                        yield btn

            # Show evidence
            if self.verdict.evidence:
                yield Label("\n[bold]Key Evidence:[/bold]", classes="av-evidence-header")
                for item in self.verdict.evidence:
                    yield Label(f"  • {item}", classes="av-evidence-item")

            # Show timing
            if self.verdict.total_evaluation_ms:
                yield Label(
                    f"\n⏱ Evaluated in {self.verdict.total_evaluation_ms}ms",
                    classes="av-timing",
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        patch_set = getattr(event.button, "_patch_set", None)
        if patch_set:
            event.stop()
            if isinstance(patch_set, MultiAgentPatchSet):
                ps = patch_set
            else:
                ps = MultiAgentPatchSet(patch_sets=[patch_set])

            # Inside a widget, use self.app — NOT app.active_app.get()
            self.app.post_message(PatchSetProposed(patch_set=ps))
