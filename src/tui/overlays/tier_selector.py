from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from src.core.quality_tiers import QualityTier


class TierSelectorOverlay(ModalScreen):
    """Overlay to select quality tier."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("1", "select_light", "Light", show=False),
        Binding("2", "select_standard", "Standard", show=False),
        Binding("3", "select_max", "Max", show=False),
    ]

    DEFAULT_CSS = """
    TierSelectorOverlay {
        align: center middle;
        background: $background 80%;
    }
    #tier-dialog {
        width: 65;
        max-width: 90%;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    #tier-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
        border-bottom: solid $secondary;
        padding-bottom: 1;
    }
    .tier-box {
        margin: 1 0;
        padding: 1 2;
        border: solid $secondary;
    }
    .tier-box:hover {
        border: solid $primary;
    }
    .tier-box.-active {
        border: solid $primary;
        background: $panel;
    }
    .tier-check {
        color: $success;
        text-style: bold;
        width: 3;
        content-align: center middle;
    }
    .tier-desc {
        color: $text-muted;
        padding-left: 2;
    }
    .tier-shortcut {
        color: $text-muted;
        text-align: right;
        width: 100%;
    }
    """

    def __init__(self, current_tier: QualityTier, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_tier = current_tier

    def action_select_light(self) -> None:
        self.dismiss(QualityTier.LIGHT)

    def action_select_standard(self) -> None:
        self.dismiss(QualityTier.STANDARD)

    def action_select_max(self) -> None:
        self.dismiss(QualityTier.MAX)

    def compose(self) -> ComposeResult:
        from textual.containers import Horizontal as _H
        with Vertical(id="tier-dialog"):
            yield Label("Select Quality Tier", id="tier-title")
            yield Label("Press [bold]1[/bold] / [bold]2[/bold] / [bold]3[/bold] or click to select", classes="tier-shortcut")

            # ── Light ──────────────────────────────────
            is_light = self.current_tier == QualityTier.LIGHT
            with Vertical(classes=f"tier-box{' -active' if is_light else ''}"):
                with _H():
                    yield Label("✓" if is_light else " ", classes="tier-check")
                    yield Label("[bold]💡 LIGHT[/bold] — [dim]Press 1[/dim]")
                yield Label(
                    "Models: DeepSeek V3, GPT-4o Mini, Gemini Flash\n"
                    "Best for: Simple tasks, explanations, high volume\n"
                    "Typical cost: ~$0.01 per task",
                    classes="tier-desc",
                )
                yield Button("Select Light  [dim]1[/dim]", id="btn-light", variant="default")

            # ── Standard ───────────────────────────────
            is_std = self.current_tier == QualityTier.STANDARD
            with Vertical(classes=f"tier-box{' -active' if is_std else ''}"):
                with _H():
                    yield Label("✓" if is_std else " ", classes="tier-check")
                    yield Label("[bold]⚡ STANDARD[/bold] — Best value ★  [dim]Press 2[/dim]")
                yield Label(
                    "Models: Claude Sonnet, GPT-4o, Gemini Pro\n"
                    "Best for: Everyday coding tasks\n"
                    "Typical cost: ~$0.04 per task",
                    classes="tier-desc",
                )
                yield Button("Select Standard  [dim]2[/dim]", id="btn-standard", variant="primary")

            # ── Max ────────────────────────────────────
            is_max = self.current_tier == QualityTier.MAX
            with Vertical(classes=f"tier-box{' -active' if is_max else ''}"):
                with _H():
                    yield Label("✓" if is_max else " ", classes="tier-check")
                    yield Label("[bold]🔥 MAX[/bold] — Maximum quality  [dim]Press 3[/dim]")
                yield Label(
                    "Models: Claude Opus, GPT-4, Gemini Pro Deep Think\n"
                    "Best for: Architecture, critical production code\n"
                    "Typical cost: ~$0.12 per task",
                    classes="tier-desc",
                )
                yield Button("Select Max  [dim]3[/dim]", id="btn-max", variant="warning")

            yield Button("Close  [dim]Esc[/dim]", id="btn-close", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-light":
            self.dismiss(QualityTier.LIGHT)
        elif event.button.id == "btn-standard":
            self.dismiss(QualityTier.STANDARD)
        elif event.button.id == "btn-max":
            self.dismiss(QualityTier.MAX)
        elif event.button.id == "btn-close":
            self.dismiss()
