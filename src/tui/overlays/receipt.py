from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class BuildReceipt(ModalScreen[None]):
    """
    Shareable receipt proving the exact cost, time saved, and model
    that successfully won the local arena match and built the feature.
    """

    DEFAULT_CSS = """
    BuildReceipt {
        align: center middle;
        background: $background 50%;
    }

    #receipt-container {
        width: 60;
        height: auto;
        padding: 2 4;
        background: $surface;
        border: thick $success;
    }

    .receipt-header {
        text-align: center;
        text-style: bold;
        color: $success;
        margin-bottom: 1;
    }

    .receipt-row {
        layout: horizontal;
        height: 1;
        margin-bottom: 1;
    }

    .receipt-label {
        width: 1fr;
        color: $text-muted;
    }

    .receipt-value {
        width: 1fr;
        text-align: right;
        text-style: bold;
    }

    #receipt-buttons {
        margin-top: 2;
        width: 100%;
        align: center middle;
    }

    #receipt-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        winner_name: str,
        loser_names: list[str],
        duration_sec: float,
        cost: float,
        files_changed: int,
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.winner_name = winner_name
        self.loser_names = loser_names
        self.duration_sec = duration_sec
        self.cost = cost
        self.files_changed = files_changed

    def compose(self) -> ComposeResult:
        with Vertical(id="receipt-container"):
            yield Static("✅  VERIFICATION BUNDLE COMPILED", classes="receipt-header")
            yield Static("=" * 50, classes="receipt-header")

            # Rows
            with Horizontal(classes="receipt-row"):
                yield Static("Winning Model:", classes="receipt-label")
                yield Static(self.winner_name, classes="receipt-value")

            if self.loser_names:
                with Horizontal(classes="receipt-row"):
                    yield Static("Defeated:", classes="receipt-label")
                    yield Static(", ".join(self.loser_names), classes="receipt-value")

            with Horizontal(classes="receipt-row"):
                yield Static("Files Patched:", classes="receipt-label")
                yield Static(str(self.files_changed), classes="receipt-value")

            with Horizontal(classes="receipt-row"):
                yield Static("Duration:", classes="receipt-label")
                yield Static(f"{self.duration_sec:.1f}s", classes="receipt-value")

            with Horizontal(classes="receipt-row"):
                yield Static("Compute Cost:", classes="receipt-label")
                yield Static(f"${self.cost:.4f}", classes="receipt-value")

            with Horizontal(id="receipt-buttons"):
                yield Button("📋 Copy Receipt", id="btn-copy-receipt", variant="primary")
                yield Button("Continue", id="btn-close-receipt", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close-receipt":
            self.dismiss()
        elif event.button.id == "btn-copy-receipt":
            # Just dismiss for now since pyperclip isn't guaranteed, but normally we'd copy
            try:
                import pyperclip
                receipt_text = (
                    f"✅ VERIFICATION BUNDLE COMPILED\n"
                    f"Winner: {self.winner_name}\n"
                    f"Cost: ${self.cost:.4f}\n"
                    f"Files Patched: {self.files_changed}\n"
                )
                pyperclip.copy(receipt_text)
                self.app.notify("Receipt copied to clipboard!", severity="information")
            except ImportError:
                self.app.notify("pyperclip not installed. Cannot copy.", severity="error")

            self.dismiss()
