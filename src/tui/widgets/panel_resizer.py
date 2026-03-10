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
        color: $surface;
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
        self._drag_start_x: int | None = None
        self._start_left_width = 0
        self._start_right_width = 0

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
        self._drag_start_x = event.screen_x
        self._start_left_width = lw
        self._start_right_width = rw

        self._click_count += 1
        self.set_timer(0.3, self._clear_click)
        event.stop()

    def _clear_click(self) -> None:
        if self._click_count < 2:
            self._click_count = 0

    def on_mouse_move(self, event: MouseMove) -> None:
        if not self._dragging or not self._left_panel or not self._right_panel:
            return

        if self._drag_start_x is None:
            return

        # Use absolute mouse movement from drag start because event.delta_x can
        # be zero/inconsistent across terminal emulators during capture.
        dx = event.screen_x - self._drag_start_x
        if dx == 0:
            return

        lw = self._start_left_width + dx
        rw = self._start_right_width - dx

        # Clamp to 5px min for both panels
        total = self._start_left_width + self._start_right_width
        if total < 10:
            return
        # noqa: W293
        lw = max(5, min(total - 5, lw))
        rw = total - lw

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
            else:
                if self._left_panel and self._right_panel and self.parent:
                    # Normalize against visible panel widths only (exclude resizers)
                    # so saved proportions stay stable across layouts/theme changes.
                    siblings = [
                        child for child in self.parent.children if not isinstance(child, PanelResizer) and child.display
                    ]  # noqa: E501
                    total_panel_w = sum(child.outer_size.width for child in siblings)
                    if total_panel_w > 0:
                        lw_pct = self._left_panel.outer_size.width / total_panel_w
                        rw_pct = self._right_panel.outer_size.width / total_panel_w
                        self.post_message(
                            self.ResizeComplete(
                                left_id=self.left_panel_id,
                                left_pct=lw_pct,
                                right_id=self.right_panel_id,
                                right_pct=rw_pct,
                            )
                        )

            self._click_count = 0
            self._left_panel = None
            self._right_panel = None
            self._drag_start_x = None
            self._start_left_width = 0
            self._start_right_width = 0
            event.stop()

    class ResetLayout(Message):
        """Fired on double click to reset defaults"""

    class ResizeComplete(Message):
        """Fired when drag finishes so app can save state"""

        def __init__(self, left_id: str, left_pct: float, right_id: str, right_pct: float):
            self.left_id = left_id
            self.left_pct = left_pct
            self.right_id = right_id
            self.right_pct = right_pct
            super().__init__()
