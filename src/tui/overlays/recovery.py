from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from src.core.logger import get_logger

logger = get_logger("tui.recovery")


class CrashRecoveryScreen(ModalScreen[bool]):
    """
    Screen shown when running.lock is detected on startup indicating the application
    did not exit gracefully in a previous session.

    Returns True if user wants to recover, False if they want to start fresh.
    """

    DEFAULT_CSS = """
    CrashRecoveryScreen {
        align: center middle;
        background: $background 80%;
    }

    #recovery-dialog {
        width: 60;
        height: auto;
        background: $panel;
        border: thick $primary;
        padding: 2 4;
    }

    #recovery-title {
        content-align: center middle;
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }

    #recovery-message {
        content-align: center middle;
        margin-bottom: 2;
    }

    #recovery-buttons {
        align: center middle;
        height: auto;
        gap: 2;
    }

    Button {
        min-width: 16;
    }
    """

    def __init__(self, state_summary: str = "Unsaved tokens or diffs detected.") -> None:
        super().__init__()
        self.state_summary = state_summary

    def compose(self) -> ComposeResult:
        with Vertical(id="recovery-dialog"):
            yield Static("⚠️ Unexpected Shutdown Detected", id="recovery-title")
            yield Static(
                f"It looks like gptcgt closed unexpectedly during your last session.\n\n"
                f"Recovery data: {self.state_summary}\n\n"
                f"Would you like to recover this state or start a fresh session?",
                id="recovery-message",
            )
            with Horizontal(id="recovery-buttons"):
                yield Button("Start Fresh (Discard)", id="btn-discard", variant="error")
                yield Button("Recover Session", id="btn-recover", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        logger.debug(f"Crash recovery choice: {event.button.id}")
        if event.button.id == "btn-discard":
            self.dismiss(False)
        elif event.button.id == "btn-recover":
            self.dismiss(True)
