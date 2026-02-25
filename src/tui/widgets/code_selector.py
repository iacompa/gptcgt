"""
Code selection system for Select-to-Prompt.

Provides CodeLineWidget (individual clickable line) and SelectionManager
(tracks multi-line selection state with keyboard and mouse support).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Click
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
        padding: 0 1;
    }
    .code-line-number {
        width: 6;
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
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.line_number = line_number
        self._raw_content = content
        self._highlighted_content = highlighted_content
        self._annotation = annotation

    def compose(self) -> ComposeResult:
        """Render the line with gutter number, annotation, and content."""
        yield Static(f"{self.line_number:4} │ ", classes="code-line-number")
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
                t.stylize("on #264F78")
                self.content_static.update(t)
        else:
            self.remove_class("code-line-selected")
            if hasattr(self, "content_static"):
                self.content_static.update(Text.from_ansi(self._highlighted_content))

    def on_click(self, event: Click) -> None:
        """Handle click events -- post to parent for selection logic."""
        self.post_message(
            CodeLineClicked(
                line_number=self.line_number,
                shift_held=event.shift,
                ctrl_held=event.ctrl,
            )
        )
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
