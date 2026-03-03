"""
Context chips bar for the chat panel.

Shows attached files and code selections as removable chips below the chat input.
Subscribes to FileRelevanceUpdated and CodeSelectionMade events.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Click
from textual.message import Message
from textual.widgets import Label, Static

from src.core.events import ContextModified
from src.core.logger import get_logger

logger = get_logger("tui.context_chips")


class ContextChip(Horizontal):
    """
    A single context chip representing a file or code selection.

    Displays a label (filename or selection description) with a remove button.
    Clicking the x removes the chip and emits ContextModified.
    """

    DEFAULT_CSS = """
    ContextChip {
        height: 1;
        width: auto;
        margin: 0 1 0 0;
        padding: 0 1;
        background: $panel;
        border: blank;
        color: $text;
        layout: horizontal;
    }
    ContextChip:hover {
        background: $surface;
        text-style: bold;
    }
    .chip-remove {
        color: $error;
        margin-left: 1;
    }
    .chip-remove:hover {
        color: #FF7B72;
        text-style: bold;
    }
    """

    def __init__(
        self,
        file_path: str,
        label_text: str,
        chip_type: str = "file",
        line_range: tuple[int, int] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.file_path = file_path
        self.label_text = label_text
        self.chip_type = chip_type  # "file" or "selection"
        self.line_range = line_range

    def compose(self) -> ComposeResult:
        yield Label(f"{self.label_text}", classes="chip-label")
        yield Label(" x", classes="chip-remove")

    def on_click(self, event: Click) -> None:
        """Handle clicks -- check if the x button was clicked."""
        if isinstance(event.widget, Label) and "chip-remove" in event.widget.classes:
            action = "remove_file" if self.chip_type == "file" else "remove_selection"
            # Clean up parent's tracking dict before removing DOM node
            parent = self.parent
            if parent and hasattr(parent, "remove_chip_by_path"):
                parent.remove_chip_by_path(self.file_path, self.line_range)
            self.post_message(
                ContextModified(
                    action=action,
                    file_path=self.file_path,
                    line_range=self.line_range,
                )
            )
            self.remove()
            event.stop()


class AddFileChip(Static):
    """A special chip that opens a file picker to add context."""

    DEFAULT_CSS = """
    AddFileChip {
        height: 1;
        width: auto;
        padding: 0 1;
        background: transparent;
        color: $primary;
        border: blank;
    }
    AddFileChip:hover {
        background: $surface;
        text-style: bold;
    }
    """

    class AddFileRequested(Message):
        """Emitted when user clicks the [+ Add file] chip."""

        def __init__(self) -> None:
            super().__init__()

    def render(self) -> str:
        return "[+ Add file]"

    def on_click(self, event: Click) -> None:
        self.post_message(self.AddFileRequested())
        event.stop()


class ContextChipBar(Horizontal):
    """
    Container for context chips, displayed below chat input header.

    Manages the list of active context files and selections.
    Provides get_context_summary() for inclusion in task prompts.
    """

    DEFAULT_CSS = """
    ContextChipBar {
        height: auto;
        min-height: 0;
        max-height: 3;
        width: 100%;
        padding: 0 1;
        overflow-x: auto;
        display: none;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._context_files: dict[str, dict] = {}  # file_path -> {label, chip_type, line_range}

    def compose(self) -> ComposeResult:
        return
        yield  # Make this a generator that yields nothing

    def add_file_chip(self, file_path: str) -> None:
        """Add a file context chip."""
        if file_path in self._context_files:
            return  # Already added
        label = Path(file_path).name
        chip = ContextChip(
            file_path=file_path,
            label_text=f"@{label}",
            chip_type="file",
            id=f"chip-{hash(file_path) & 0xFFFFFFFF}",
        )
        self._context_files[file_path] = {"label": label, "chip_type": "file", "line_range": None}
        self.mount(chip)
        self._update_visibility()

    def add_selection_chip(self, file_path: str, start_line: int, end_line: int) -> None:
        """Add a code selection context chip."""
        key = f"{file_path}:{start_line}-{end_line}"
        if key in self._context_files:
            return
        filename = Path(file_path).name
        label = f"{filename}:{start_line}-{end_line}"
        chip = ContextChip(
            file_path=file_path,
            label_text=label,
            chip_type="selection",
            line_range=(start_line, end_line),
            id=f"chip-{hash(key) & 0xFFFFFFFF}",
        )
        self._context_files[key] = {
            "label": label,
            "chip_type": "selection",
            "line_range": (start_line, end_line),
        }
        self.mount(chip)
        self._update_visibility()

    def remove_chip_by_path(
        self, file_path: str, line_range: tuple[int, int] | None = None
    ) -> None:
        """Remove a chip by file path and optional line range."""
        if line_range:
            key = f"{file_path}:{line_range[0]}-{line_range[1]}"
        else:
            key = file_path
        if key in self._context_files:
            del self._context_files[key]
        self._update_visibility()

    def get_context_summary(self) -> list[dict]:
        """
        Return the current context for inclusion in task prompts.

        Returns:
            List of dicts with keys: file_path, chip_type, line_range (optional).

        """
        result = []
        for key, info in self._context_files.items():
            entry = {
                "file_path": key.split(":")[0]
                if ":" in key and info["chip_type"] == "selection"
                else key,
                "chip_type": info["chip_type"],
            }
            if info.get("line_range"):
                entry["line_range"] = info["line_range"]
            result.append(entry)
        return result

    def clear_all(self) -> None:
        """Remove all context chips."""
        for child in list(self.children):
            if isinstance(child, ContextChip):
                child.remove()
        self._context_files.clear()
        self._update_visibility()

    def _update_visibility(self) -> None:
        """Show bar only when chips exist, collapse fully when empty."""
        has_chips = bool(self._context_files)
        self.display = has_chips
