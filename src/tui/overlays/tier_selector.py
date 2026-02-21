from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical
from textual.widgets import Label, Button

from src.core.quality_tiers import QualityTier

class TierSelectorOverlay(ModalScreen):
    """Overlay to select quality tier."""

    DEFAULT_CSS = """
    TierSelectorOverlay {
        align: center middle;
        background: $background 80%;
    }
    #tier-dialog {
        width: 60%;
        height: auto;
        background: #1C2333;
        border: solid #58A6FF;
        padding: 1 2;
    }
    .tier-box {
        margin: 1 0;
        padding: 1;
        border: solid #30363D;
    }
    .tier-box.-active {
        border: solid #58A6FF;
        background: #232D40;
    }
    """

    def __init__(self, current_tier: QualityTier, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_tier = current_tier

    def compose(self) -> ComposeResult:
        with Vertical(id="tier-dialog"):
            yield Label("Quality Tier", classes="text-primary text-style-bold")
            
            with Vertical(classes=f"tier-box {' -active' if self.current_tier == QualityTier.LIGHT else ''}"):
                yield Label("💡 LIGHT — Budget-friendly")
                yield Label("Uses: DeepSeek V3, GPT-4o Mini, Gemini Flash\nBest for: Simple tasks, high volume\nTypical cost: ~$0.01", classes="text-secondary")
                yield Button("Select Light", id="btn-light")
                
            with Vertical(classes=f"tier-box {' -active' if self.current_tier == QualityTier.STANDARD else ''}"):
                yield Label("⚡ STANDARD — Best value (recommended)")
                yield Label("Uses: Claude Sonnet, GPT-4o, Gemini Pro\nBest for: Everyday development\nTypical cost: ~$0.04", classes="text-secondary")
                yield Button("Select Standard", id="btn-standard")
                
            with Vertical(classes=f"tier-box {' -active' if self.current_tier == QualityTier.MAX else ''}"):
                yield Label("🔥 MAX — Maximum quality")
                yield Label("Uses: Claude Opus, GPT-4, Gemini Pro Deep Think\nBest for: Critical code, architecture\nTypical cost: ~$0.12", classes="text-secondary")
                yield Button("Select Max", id="btn-max")
                
            yield Button("Close", id="btn-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-light":
            self.dismiss(QualityTier.LIGHT)
        elif event.button.id == "btn-standard":
            self.dismiss(QualityTier.STANDARD)
        elif event.button.id == "btn-max":
            self.dismiss(QualityTier.MAX)
        elif event.button.id == "btn-close":
            self.dismiss()
