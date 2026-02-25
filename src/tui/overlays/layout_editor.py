from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class LayoutEditorOverlay(ModalScreen[str]):
    """
    Overlay to select structural layout presets.
    Returns the selected layout name string.
    """

    DEFAULT_CSS = """
    LayoutEditorOverlay {
        align: center middle;
    }

    #layout-dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $primary;
    }

    .layout-btn {
        width: 100%;
        margin-bottom: 1;
    }

    .layout-preview {
        height: 3;
        margin-top: 1;
        layout: horizontal;
    }
    .preview-box {
        height: 100%;
        border: solid $panel-lighten-2;
        content-align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="layout-dialog"):
            yield Label("[b]Select Layout Preset[/b]", id="layout-title")
            yield Button("Default (Tree | Code | Chat)", id="btn-default", classes="layout-btn")
            yield Button("Code Focus (Code | Chat)", id="btn-code_focus", classes="layout-btn")
            yield Button("Review (Tree | Code)", id="btn-review", classes="layout-btn")
            yield Button("Chat Focus (Tree | Chat)", id="btn-chat_focus", classes="layout-btn")
            yield Button("Cancel", id="btn-cancel", variant="error", classes="layout-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-cancel":
            self.dismiss()
        else:
            layout_name = btn_id.replace("btn-", "")
            self.dismiss(layout_name)
