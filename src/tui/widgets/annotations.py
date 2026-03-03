# ruff: noqa: E501

"""
Inline code annotations system.
Provides widgets to display AI-generated insights, warnings, and suggestions
directly alongside the code lines.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.message import Message
from textual.widgets import Button, Label, Static

from src.core.events import AnnotationActionClicked
from src.core.logger import get_logger

logger = get_logger("tui.annotations")


@dataclass
class CodeAnnotation:
    """Represents a single parsed annotation."""

    line_number: int
    severity: str  # "info", "warning", "error"
    message: str
    actions: list[str]


class AnnotationGutter(Static):
    """A small indicator in the code gutter showing an annotation exists."""

    DEFAULT_CSS = """
    AnnotationGutter {
        width: 4;
        height: 1;
        content-align: center middle;
        text-style: bold;
    }
    AnnotationGutter.severity-info { color: $primary; }
    AnnotationGutter.severity-warning { color: $warning; }
    AnnotationGutter.severity-error { color: $error; }
    AnnotationGutter.clickable:hover { background: $secondary; }
    """

    class Clicked(Message):
        """Emitted when the gutter icon is clicked."""

        def __init__(self, annotation: CodeAnnotation | None) -> None:
            self.annotation = annotation
            super().__init__()

    def __init__(self, annotation: CodeAnnotation | None = None, **kwargs) -> None:
        super().__init__("", **kwargs)
        self.annotation = annotation

    def on_mount(self) -> None:
        self.update_display()

    def update_display(self) -> None:
        if not self.annotation:
            self.update(" ")
            self.remove_class("severity-info", "severity-warning", "severity-error", "clickable")
            self.tooltip = None
            self.display = False  # Hide gutter entirely when empty
        else:
            self.display = True
            icons = {"info": "ℹ️", "warning": "⚠️", "error": "✖"}
            sev = self.annotation.severity if self.annotation.severity in icons else "info"
            self.update(icons.get(sev, "•"))
            self.add_class(f"severity-{sev}", "clickable")
            # Tooltip shows preview of message (first 80 chars)
            preview = self.annotation.message[:80]
            if len(self.annotation.message) > 80:
                preview += "..."
            self.tooltip = f"Line {self.annotation.line_number}: {preview}"

    def set_annotation(self, annotation: CodeAnnotation | None) -> None:
        self.annotation = annotation
        self.update_display()

    def on_click(self, event: Click) -> None:
        if self.annotation:
            self.post_message(self.Clicked(self.annotation))
            event.stop()


class AnnotationPanel(Vertical):
    """An inline panel displaying the annotation details and actions."""

    DEFAULT_CSS = """
    AnnotationPanel {
        width: 100%;
        height: auto;
        padding: 1 2;
        background: $surface;
        border-right: solid $primary;
        border-bottom: solid $secondary;
        margin-bottom: 1;
    }
    .annotation-message { margin-bottom: 1; color: $text; }
    .annotation-actions { height: auto; layout: horizontal; }
    .annotation-action-btn { margin-right: 1; height: 1; border: none; min-width: 10; background: #264F78; }  # noqa: E501
    .annotation-action-btn:hover { background: $primary; }
    """

    class Closed(Message):
        """Emitted when the panel should be closed."""

        def __init__(self) -> None:
            super().__init__()

    def __init__(self, annotation: CodeAnnotation, file_path: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.annotation = annotation
        self.file_path = file_path

    def compose(self) -> ComposeResult:
        severity_colors = {"info": "$primary", "warning": "$warning", "error": "$error"}
        color = severity_colors.get(self.annotation.severity, "$text")

        yield Label(
            f"[{color}][bold]{self.annotation.severity.upper()}[/bold][/{color}] — Line {self.annotation.line_number}"  # noqa: E501
        )
        yield Label(self.annotation.message, classes="annotation-message")

        action_container = Horizontal(classes="annotation-actions")
        with action_container:
            for action in self.annotation.actions:
                btn = Button(action, classes="annotation-action-btn")
                btn._annotation_action_name = action
                yield btn

            close_btn = Button(
                "Close", id="btn-close-annotation", classes="annotation-action-btn", variant="error"
            )
            yield close_btn

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close-annotation":
            self.post_message(self.Closed())
            return

        action_name = getattr(event.button, "_annotation_action_name", None)
        if action_name:
            self.post_message(
                AnnotationActionClicked(
                    action=action_name,
                    file_path=self.file_path,
                    line_number=self.annotation.line_number,
                    context={"message": self.annotation.message},
                )
            )
            # Close panel after invoking action
            self.post_message(self.Closed())


class AnnotationManager:
    """Manages the state of annotations for a given file."""

    def __init__(self) -> None:
        self._annotations: dict[int, CodeAnnotation] = {}
        self._visible = True

    @property
    def is_visible(self) -> bool:
        return self._visible

    def toggle_visibility(self) -> None:
        self._visible = not self._visible

    def load_annotations(self, raw_annotations: list[dict]) -> None:
        self._annotations.clear()
        for ann in raw_annotations:
            line = ann.get("line_number", 0)
            if line > 0:
                self._annotations[line] = CodeAnnotation(
                    line_number=line,
                    severity=ann.get("severity", "info"),
                    message=ann.get("message", "No description provided."),
                    actions=ann.get("actions", []),
                )

    def get_annotation(self, line_number: int) -> CodeAnnotation | None:
        return self._annotations.get(line_number) if self._visible else None

    def has_annotation(self, line_number: int) -> bool:
        return line_number in self._annotations if self._visible else False
