from __future__ import annotations

from textual.events import MouseDown, MouseMove, MouseUp
from textual.message import Message
from textual.widget import Widget


class PanelResizer(Widget):
    """A draggable vertical bar for resizing adjacent panels."""

    DEFAULT_CSS = """
    PanelResizer {
        width: 1;
        height: 100%;
        background: transparent;
        color: $surface-light;
        content-align: center middle;
    }

    PanelResizer:hover {
        color: $primary;
    }

    PanelResizer.-dragging {
        color: $primary;
    }
    """

    def render(self) -> str:
        # A simple thin vertical line pattern
        return "│\n" * self.size.height

    def __init__(self, left_panel_id: str, right_panel_id: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.left_panel_id = left_panel_id
        self.right_panel_id = right_panel_id
        self._dragging = False
        self._click_count = 0
        self._left_panel = None
        self._right_panel = None

    def on_mouse_down(self, event: MouseDown) -> None:
        if event.button != 1:
            return

        self.capture_mouse()
        self._dragging = True
        self.add_class("-dragging")

        # Cache panel refs — avoids re-querying DOM on every move
        self._left_panel = self.screen.query_one(f"#{self.left_panel_id}")
        self._right_panel = self.screen.query_one(f"#{self.right_panel_id}")

        # Snapshot current pixel widths and lock them in
        lw = self._left_panel.outer_size.width
        rw = self._right_panel.outer_size.width
        self._left_panel.styles.width = lw
        self._right_panel.styles.width = rw

        self._click_count += 1
        self.set_timer(0.3, self._clear_click)
        event.stop()

    def _clear_click(self) -> None:
        if self._click_count < 2:
            self._click_count = 0

    def on_mouse_move(self, event: MouseMove) -> None:
        if not self._dragging or not self._left_panel or not self._right_panel:
            return

        dx = event.delta_x
        if dx == 0:
            return

        lw = self._left_panel.outer_size.width + dx
        rw = self._right_panel.outer_size.width - dx

        # Clamp to minimums
        if lw < 15 or rw < 15:
            return

        self._left_panel.styles.width = lw
        self._right_panel.styles.width = rw
        event.stop()

    def on_mouse_up(self, event: MouseUp) -> None:
        if self._dragging:
            self.release_mouse()
            self._dragging = False
            self.remove_class("-dragging")

            if self._click_count == 2:
                # Double-click resets layout
                self.post_message(self.ResetLayout())

            self._click_count = 0
            self._left_panel = None
            self._right_panel = None
            self.post_message(self.ResizeComplete())
            event.stop()

    class ResetLayout(Message):
        """Fired on double click to reset defaults"""

    class ResizeComplete(Message):
        """Fired when drag finishes so app can save state"""
