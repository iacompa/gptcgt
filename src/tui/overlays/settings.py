"""Settings overlay for persistent chat and other features."""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, Switch, Select

class SettingsOverlay(ModalScreen):
    """Modal overlay to configure application settings."""

    DEFAULT_CSS = """
    SettingsOverlay {
        align: center middle;
        background: $background 80%;
    }
    #settings-dialog {
        width: 60%;
        height: 60%;
        background: #1C2333;
        border: solid #58A6FF;
        padding: 1 2;
    }
    .settings-title {
        text-style: bold;
        margin-bottom: 2;
        color: #E6EDF3;
    }
    .setting-row {
        height: auto;
        margin-bottom: 1;
        align: space-between middle;
    }
    .setting-label {
        color: #E6EDF3;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-dialog"):
            yield Label("Settings", classes="settings-title")
            
            with Horizontal(classes="setting-row"):
                yield Label("Continue last session on launch", classes="setting-label")
                yield Switch(value=True, id="switch-continue-session")
                
            with Horizontal(classes="setting-row"):
                yield Label("Chat auto-saves every message", classes="setting-label")
                yield Label("✓ Active", classes="setting-info")
                
            with Horizontal(classes="setting-row"):
                yield Label("Session retention (days)", classes="setting-label")
                yield Select(
                    [("30", "30"), ("60", "60"), ("90", "90"), ("365", "365"), ("Forever", "forever")],
                    value="90",
                    id="select-retention"
                )
                
            yield Button("Close", id="btn-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss()
