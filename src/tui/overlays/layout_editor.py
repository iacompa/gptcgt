from __future__ import annotations  # noqa: I001

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label

class LayoutEditorOverlay(ModalScreen[None]):
    """
    Overlay to select panel placements (Left, Center, Right, Top, Bottom).
    Changes are applied instantly to the active app config.
    Shows current position for each panel and disables occupied slots.
    """

    DEFAULT_CSS = """
    LayoutEditorOverlay {
        align: center middle;
    }

    #layout-dialog {
        width: 90;
        max-height: 80vh;
        padding: 2 3;
        background: $surface;
        border: thick $primary;
    }

    #layout-scroll {
        height: auto;
        max-height: 100%;
    }

    #layout-title {
        margin-bottom: 2;
    }

    .layout-row {
        height: 3;
        margin-bottom: 1;
        align: left middle;
    }

    .panel-label {
        width: 18;
        content-align: left middle;
        text-style: bold;
    }

    .pos-badge {
        width: 10;
        content-align: center middle;
        color: $primary;
        text-style: italic;
        margin-right: 1;
    }

    .dir-btn {
        margin-right: 1;
        min-width: 12;
    }

    .close-btn {
        width: 100%;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        positions = {}
        if hasattr(self.app, "config"):
            positions = getattr(self.app.config.user, "panel_positions",
                                {"files": "left", "code": "center", "chat": "right"})

        with Vertical(id="layout-dialog"):
            yield Label("[b]Customize Layout Positions[/b]\nChanges apply instantly.", id="layout-title")

            with VerticalScroll(id="layout-scroll"):
                for panel, label in [("files", "Files/Tree"), ("code", "Code View"), ("chat", "Chat")]:
                    current_pos = positions.get(panel, "left").title()
                    with Horizontal(classes="layout-row"):
                        yield Label(label, classes="panel-label")
                        yield Label(f"[{current_pos}]", classes="pos-badge", id=f"badge-{panel}")
                        for direction in ["left", "center", "right", "top", "bottom"]:
                            btn = Button(
                                direction.title(),
                                id=f"btn-{panel}-{direction}",
                                classes="dir-btn",
                                disabled=(positions.get(panel) == direction),
                            )
                            yield btn

            yield Button("Close", id="btn-close", variant="primary", classes="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-close":
            self.dismiss()
        elif btn_id.startswith("btn-"):
            parts = btn_id.split("-")
            if len(parts) == 3:
                panel_key = parts[1]
                direction = parts[2]
                if hasattr(self.app, "action_move_panel"):
                    self.app.action_move_panel(panel_key, direction)
                    self._refresh_positions()

    def _refresh_positions(self) -> None:
        """Update position badges and button disabled states after a move."""
        positions = {}
        if hasattr(self.app, "config"):
            positions = getattr(self.app.config.user, "panel_positions",
                                {"files": "left", "code": "center", "chat": "right"})

        for panel in ["files", "code", "chat"]:
            current_pos = positions.get(panel, "left")
            try:
                badge = self.query_one(f"#badge-{panel}", Label)
                badge.update(f"[{current_pos.title()}]")
            except Exception:
                pass

            for direction in ["left", "center", "right", "top", "bottom"]:
                try:
                    btn = self.query_one(f"#btn-{panel}-{direction}", Button)
                    btn.disabled = (current_pos == direction)
                except Exception:
                    pass
