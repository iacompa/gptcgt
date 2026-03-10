"""
Mode Picker Overlay — Ctrl+M

Lets the user switch between STANDARD, ENSEMBLE, BATTLE, and ARCHITECT modes
with full descriptions and keyboard shortcuts.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from src.core.logger import get_logger
from src.core.mode_manager import CREDIT_COSTS, OperationMode

logger = get_logger("tui.mode_picker")

_MODES = [
    (
        OperationMode.STANDARD,
        "🤖",
        "STANDARD",
        "Single best AI for the task",
        (
            "The orchestrator picks the optimal model for your prompt and tier.\n"
            "Fast, predictable, cost-effective for everyday coding."
        ),
        "$0.02–$0.08",
    ),
    (
        OperationMode.ENSEMBLE,
        "🚀",
        "ENSEMBLE",
        "Multiple AIs vote on the best answer",
        (
            "2-3 models solve the problem in parallel. An Arbiter evaluates\n"
            "each patch across 6 dimensions and picks the winner."
        ),
        "$0.10–$0.30",
    ),
    (
        OperationMode.BATTLE,
        "⚔️",
        "BATTLE",
        "Two AIs compete head-to-head",
        (
            "Two models generate competing solutions shown side by side.\n"
            "Arbiter declares a winner. Great for hard algorithmic problems."
        ),
        "$0.08–$0.25",
    ),
    (
        OperationMode.ARCHITECT,
        "🏗️",
        "ARCHITECT",
        "AI plans first — you approve — then it builds",
        (
            "AI produces an implementation plan. You review and approve (or reject)\n"
            "before any code is written. Best for large new features."
        ),
        "$0.15–$0.50",
    ),
    (
        OperationMode.SCOUT,
        "🔍",
        "SCOUT",
        "Fast analysis, no code changes",
        (
            "Cheap, quick model explains, audits, or answers questions.\n"
            "Never writes to disk. Use to understand code before acting."
        ),
        "$0.005–$0.02",
    ),
]


class ModePickerOverlay(ModalScreen):
    """Full-featured mode picker with descriptions, cost estimates, and keyboard shortcuts."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("1", "pick_1", "Standard", show=False),
        Binding("2", "pick_2", "Ensemble", show=False),
        Binding("3", "pick_3", "Battle", show=False),
        Binding("4", "pick_4", "Architect", show=False),
        Binding("5", "pick_5", "Scout", show=False),
    ]

    DEFAULT_CSS = """
    ModePickerOverlay {
        align: center middle;
        background: $background 80%;
    }
    #mode-dialog {
        width: 72;
        max-width: 95%;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    #mode-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
        border-bottom: solid $secondary;
        padding-bottom: 1;
        width: 100%;
    }
    .mode-box {
        margin: 0 0 1 0;
        padding: 1 2;
        border: solid $secondary;
    }
    .mode-box:hover {
        border: solid $primary;
    }
    .mode-box.-active {
        border: solid $primary;
        background: $panel;
    }
    .mode-row {
        height: auto;
        align: left middle;
    }
    .mode-check {
        color: $success;
        text-style: bold;
        width: 3;
        content-align: center middle;
    }
    .mode-name {
        text-style: bold;
        color: $text;
    }
    .mode-key {
        color: $text-muted;
        width: 10;
        content-align: right middle;
    }
    .mode-tagline {
        color: $primary;
        padding-left: 3;
        margin-bottom: 0;
    }
    .mode-desc {
        color: $text-muted;
        padding-left: 3;
        margin-bottom: 1;
    }
    .mode-cost {
        color: $success;
        padding-left: 3;
        text-style: italic;
    }
    .mode-cr {
        color: $warning;
        text-style: bold;
    }
    .hint-row {
        width: 100%;
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }
    """

    def __init__(self, current_mode: OperationMode, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_mode = current_mode

    def action_pick_1(self) -> None:
        self.dismiss(OperationMode.STANDARD)

    def action_pick_2(self) -> None:
        self.dismiss(OperationMode.ENSEMBLE)

    def action_pick_3(self) -> None:
        self.dismiss(OperationMode.BATTLE)

    def action_pick_4(self) -> None:
        self.dismiss(OperationMode.ARCHITECT)

    def action_pick_5(self) -> None:
        self.dismiss(OperationMode.SCOUT)

    def compose(self) -> ComposeResult:
        with Vertical(id="mode-dialog"):
            yield Label("⚙️  Select Operation Mode", id="mode-title")
            yield Label(
                "Press [bold]1–5[/bold] or click a mode to select  •  [dim]Esc[/dim] to cancel",
                classes="hint-row",
            )

            for i, (mode, icon, name, tagline, desc, cost_range) in enumerate(_MODES, 1):
                is_active = mode == self.current_mode
                cr = CREDIT_COSTS.get(mode, 5)
                with Vertical(
                    classes=f"mode-box{' -active' if is_active else ''}",
                    id=f"mode-box-{i}",
                ):
                    with Horizontal(classes="mode-row"):
                        yield Label("✓" if is_active else " ", classes="mode-check")
                        yield Label(
                            f"{icon} [bold]{name}[/bold]",
                            classes="mode-name",
                        )
                        yield Label(f"[dim]Press {i}[/dim]", classes="mode-key")
                    yield Label(tagline, classes="mode-tagline")
                    yield Label(desc, classes="mode-desc")
                    with Horizontal():
                        yield Label(f"Est. cost: {cost_range} per task", classes="mode-cost")
                        yield Label(
                            f"  [{cr} cr/task]",
                            classes="mode-cr",
                        )
                    yield Button(
                        f"Select {name}  [dim]{i}[/dim]",
                        id=f"btn-mode-{i}",
                        variant="primary" if is_active else "default",
                    )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if not event.button.id:
            self.dismiss()
            return
        if event.button.id.startswith("btn-mode-"):
            idx = int(event.button.id.split("-")[-1]) - 1
            mode = _MODES[idx][0]
            self.dismiss(mode)
