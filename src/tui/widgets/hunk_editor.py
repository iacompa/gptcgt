"""
Inline hunk editor widget. Replaces the green (added) lines of a diff hunk
with an editable TextArea so the user can modify the AI's suggestion before approving.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Label, TextArea

from src.core.logger import get_logger

logger = get_logger("tui.hunk_editor")


class HunkEditor(Vertical):
    """
    Inline editor for a single diff hunk's modified lines.

    Mount this widget in place of the green diff lines. It pre-populates
    a TextArea with the AI's proposed code. The user can edit, then
    Apply (save edits), Cancel (discard), or Reset (restore AI original).

    Attributes:
        file_path: Path of the file being diffed.
        hunk_index: Index of the hunk within the FilePatch.hunks list.
        original_ai_text: The unmodified AI suggestion (for Reset).

    """

    BINDINGS = [
        Binding("ctrl+enter", "apply_edit", "Apply Edit", priority=True),
        Binding("escape", "cancel_edit", "Cancel", priority=True),
    ]

    DEFAULT_CSS = """
    HunkEditor {
        height: auto;
        max-height: 30;
        margin: 0 0;
        padding: 0;
    }
    """

    class EditApplied(Message):
        """Posted when user applies their edits."""

        def __init__(self, file_path: str, hunk_index: int, edited_text: str) -> None:
            self.file_path = file_path
            self.hunk_index = hunk_index
            self.edited_text = edited_text
            super().__init__()

    class EditCancelled(Message):
        """Posted when user cancels editing."""

        def __init__(self, file_path: str, hunk_index: int) -> None:
            self.file_path = file_path
            self.hunk_index = hunk_index
            super().__init__()

    def __init__(
        self,
        file_path: str,
        hunk_index: int,
        modified_lines: list[str],
        language: str = "python",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.file_path = file_path
        self.hunk_index = hunk_index
        self.original_ai_text = "\n".join(modified_lines)
        self._language = language
        self._editor: TextArea | None = None

    def compose(self) -> ComposeResult:
        """Compose the editor with header, TextArea, and control buttons."""
        yield Label(
            "[bold yellow]EDITING HUNK[/bold yellow] — Modify the AI's suggestion below",
            classes="hunk-editor-header",
        )
        self._editor = TextArea(
            self.original_ai_text,
            language=self._language,
            id="hunk-edit-textarea",
            classes="hunk-editor-textarea",
        )
        self._editor.show_line_numbers = True
        yield self._editor
        with Horizontal(classes="hunk-editor-controls"):
            yield Button("Apply Edit", id="btn-hunk-apply", variant="success")
            yield Button("Cancel", id="btn-hunk-cancel", variant="default")
            yield Button("Reset to AI", id="btn-hunk-reset", variant="warning")

    def on_mount(self) -> None:
        """Focus the TextArea immediately on mount."""
        if self._editor:
            self._editor.theme = "github_light" if getattr(self.app, "theme", "") == "polar" else "vscode_dark"
            self._editor.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle control button clicks."""
        if event.button.id == "btn-hunk-apply":
            self.action_apply_edit()
        elif event.button.id == "btn-hunk-cancel":
            self.action_cancel_edit()
        elif event.button.id == "btn-hunk-reset":
            self._reset_to_original()

    def action_apply_edit(self) -> None:
        """Apply the user's edits and close the editor."""
        if self._editor:
            edited_text = self._editor.text
            logger.info(f"Hunk edit applied for {self.file_path} hunk {self.hunk_index} ({len(edited_text)} chars)")
            self.post_message(self.EditApplied(self.file_path, self.hunk_index, edited_text))

    def action_cancel_edit(self) -> None:
        """Cancel editing and close the editor."""
        logger.info(f"Hunk edit cancelled for {self.file_path} hunk {self.hunk_index}")
        self.post_message(self.EditCancelled(self.file_path, self.hunk_index))

    def _reset_to_original(self) -> None:
        """Reset the TextArea content to the original AI suggestion."""
        if self._editor:
            self._editor.text = self.original_ai_text
            self._editor.focus()
            logger.debug(f"Hunk editor reset to AI original for hunk {self.hunk_index}")

    @property
    def current_text(self) -> str:
        """Get the current content of the editor."""
        return self._editor.text if self._editor else self.original_ai_text
