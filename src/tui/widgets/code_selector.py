"""
Code selection system for Select-to-Prompt.

Provides CodeLineWidget (individual clickable line) and SelectionManager
(tracks multi-line selection state with keyboard and mouse support).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import MouseDown, MouseMove, MouseUp
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static

from src.core.logger import get_logger
from src.tui.widgets.annotations import AnnotationGutter, CodeAnnotation

logger = get_logger("tui.code_selector")


class CodeLineWidget(Horizontal):
    """
    A single line of code that can be selected.

    Each instance represents one line in the code viewer. It displays
    a line number gutter, an annotation gutter, and the syntax-highlighted code content.
    Supports click and shift-click for mouse-based selection.
    """

    DEFAULT_CSS = """
    CodeLineWidget {
        width: auto;
        min-width: 100%;
        height: auto;
        padding: 0;
    }
    .code-line-number {
        width: auto;
        height: 100%;
        color: $text-muted;
    }
    .code-line-content {
        width: auto;
        min-width: 1fr;
        height: auto;
    }
    """

    is_selected = reactive(False)
    line_number = reactive(0)

    def __init__(
        self,
        line_number: int,
        content: str,
        highlighted_content: str,
        annotation: CodeAnnotation | None = None,
        line_number_digits: int = 2,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.line_number = line_number
        self._raw_content = content
        self._highlighted_content = highlighted_content
        self._annotation = annotation
        self._line_number_digits = max(1, line_number_digits)
        self._mouse_down_pos: tuple[int, int] | None = None
        self._mouse_dragged = False

    def compose(self) -> ComposeResult:
        """Render the line with gutter number, annotation, and content."""
        number = Static(
            f"{self.line_number:>{self._line_number_digits}}│",
            classes="code-line-number",
        )
        number.styles.width = self._line_number_digits + 1
        yield number
        self._annotation_gutter = AnnotationGutter(self._annotation)
        yield self._annotation_gutter
        # Convert ANSI escape sequences to Rich Text objects for safe rendering
        from rich.text import Text

        content_text = Text.from_ansi(self._highlighted_content)
        self.content_static = Static(content_text, classes="code-line-content", markup=False)
        yield self.content_static

    def set_annotation(self, annotation: CodeAnnotation | None) -> None:
        """Update the annotation for this line."""
        self._annotation = annotation
        if hasattr(self, "_annotation_gutter"):
            self._annotation_gutter.set_annotation(annotation)

    def watch_is_selected(self, selected: bool) -> None:
        """Update visual state when selection changes."""
        from rich.text import Text

        if selected:
            self.add_class("code-line-selected")
            if hasattr(self, "content_static"):
                t = Text.from_ansi(self._highlighted_content)
                # Use the app's theme-aware primary color for selection highlight.
                # Force white text so it's readable on both dark and light themes.
                try:
                    primary = self.app.get_css_variables().get("primary", "#264F78")
                    t.stylize(f"on {primary} bold white")
                except Exception:
                    t.stylize("on #264F78 bold white")
                self.content_static.update(t)
        else:
            self.remove_class("code-line-selected")
            if hasattr(self, "content_static"):
                self.content_static.update(Text.from_ansi(self._highlighted_content))

    def on_mouse_down(self, event: MouseDown) -> None:
        if event.button != 1:
            return
        self._mouse_down_pos = (event.screen_x, event.screen_y)
        self._mouse_dragged = False
        event.stop()

    def on_mouse_move(self, event: MouseMove) -> None:
        if self._mouse_down_pos is None:
            return
        sx, sy = self._mouse_down_pos
        if abs(event.screen_x - sx) > 1 or abs(event.screen_y - sy) > 0:
            self._mouse_dragged = True
        event.stop()

    def on_mouse_up(self, event: MouseUp) -> None:
        """Handle click-like release events without triggering on drag."""
        if event.button != 1:
            self._mouse_down_pos = None
            self._mouse_dragged = False
            return
        if self._mouse_down_pos is None:
            return
        if self._mouse_dragged:
            self._mouse_down_pos = None
            self._mouse_dragged = False
            event.stop()
            return
        self.post_message(
            CodeLineClicked(
                line_number=self.line_number,
                shift_held=event.shift,
                ctrl_held=event.ctrl,
            )
        )
        self._mouse_down_pos = None
        self._mouse_dragged = False
        event.stop()


class CodeLineClicked(Message):
    """Emitted when a code line is clicked."""

    def __init__(self, line_number: int, shift_held: bool = False, ctrl_held: bool = False) -> None:
        super().__init__()
        self.line_number = line_number
        self.shift_held = shift_held
        self.ctrl_held = ctrl_held


class SelectionManager:
    """
    Manages multi-line selection state for the code viewer.

    Tracks selection start/end, provides methods for keyboard extension,
    and emits the final selection as a CodeSelectionMade event.

    Usage:
        manager = SelectionManager()
        manager.start_selection(10)      # Begin at line 10
        manager.extend_selection(15)     # Extend to line 15
        start, end = manager.get_range() # Returns (10, 15)
        manager.clear()                  # Reset
    """

    def __init__(self) -> None:
        self._anchor: int | None = None
        self._cursor: int | None = None
        self._active: bool = False

    @property
    def is_active(self) -> bool:
        """Whether selection mode is currently active."""
        return self._active

    @property
    def anchor(self) -> int | None:
        """The line where selection started."""
        return self._anchor

    @property
    def cursor(self) -> int | None:
        """The current selection cursor position."""
        return self._cursor

    def start_selection(self, line_number: int) -> None:
        """Enter selection mode and set the anchor line."""
        self._active = True
        self._anchor = line_number
        self._cursor = line_number

    def extend_selection(self, line_number: int) -> None:
        """Move the cursor to extend the selection range."""
        if not self._active:
            return
        self._cursor = line_number

    def move_cursor_down(self, max_line: int) -> None:
        """Extend selection one line down (j key or Down arrow)."""
        if not self._active or self._cursor is None:
            return
        self._cursor = min(self._cursor + 1, max_line)

    def move_cursor_up(self) -> None:
        """Extend selection one line up (k key or Up arrow)."""
        if not self._active or self._cursor is None:
            return
        self._cursor = max(self._cursor - 1, 1)

    def get_range(self) -> tuple[int, int] | None:
        """Return (start_line, end_line) of current selection, or None."""
        if not self._active or self._anchor is None or self._cursor is None:
            return None
        return (min(self._anchor, self._cursor), max(self._anchor, self._cursor))

    def is_line_selected(self, line_number: int) -> bool:
        """Check if a given line is within the selection range."""
        rng = self.get_range()
        if rng is None:
            return False
        return rng[0] <= line_number <= rng[1]

    def clear(self) -> None:
        """Exit selection mode and clear all state."""
        self._active = False
        self._anchor = None
        self._cursor = None
