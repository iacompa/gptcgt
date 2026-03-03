"""Toast notification system for non-blocking alerts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional

from textual import events
from textual.app import App
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Button, Static

from src.core.logger import get_logger

logger = get_logger("tui.toast")

Severity = Literal["info", "success", "warning", "error"]


@dataclass
class ToastMessage:
    title: str
    message: str
    severity: Severity = "info"
    timeout: float = 4.0  # seconds before auto-dismiss
    action_label: Optional[str] = None
    action_callback: Optional[Callable[[], Any]] = None


class Toast(Widget):
    """An individual transient notification."""

    DEFAULT_CSS = """
    Toast {
        width: 40;
        height: auto;
        max-height: 15;
        overflow-y: auto;
        padding: 1 2;
        margin: 1 2;
        background: $panel;
        border: solid $primary;
        opacity: 0.95;
        transition: opacity 300ms in_out_cubic;
    }

    Toast.-info { border-left: thick $primary; }
    Toast.-success { border-left: thick $success; }
    Toast.-warning { border-left: thick $warning; }
    Toast.-error { border-left: thick $error; }

    Toast.-fade-out {
        opacity: 0.0;
    }

    #toast-title {
        text-style: bold;
        margin-bottom: 1;
    }

    .toast-action {
        margin-top: 1;
        width: 100%;
        min-width: 10;
    }
    """

    def __init__(self, msg: ToastMessage) -> None:
        super().__init__()
        self.msg = msg
        self.timer = None

    def compose(self):
        yield Static(self.msg.title, id="toast-title")
        if self.msg.message:
            yield Static(self.msg.message, id="toast-message")
        if self.msg.action_label and self.msg.action_callback:
            yield Button(self.msg.action_label, classes="toast-action", variant="primary")

    def on_mount(self) -> None:
        self.add_class(f"-{self.msg.severity}")
        if self.msg.timeout > 0:
            self.timer = self.set_timer(self.msg.timeout, self._start_fade_out)

    def _start_fade_out(self) -> None:
        self.add_class("-fade-out")
        # remove entirely after animation completes
        self.set_timer(0.3, self.remove)

    def on_click(self, event: events.Click) -> None:
        """Dismiss on click."""
        if self.timer:
            self.timer.stop()
        self._start_fade_out()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle action button click."""
        event.stop()
        if self.msg.action_callback:
            self.msg.action_callback()
        if self.timer:
            self.timer.stop()
        self._start_fade_out()

    def on_enter(self, event: events.Enter) -> None:
        """Pause auto-dismiss on hover."""
        if self.timer:
            self.timer.pause()

    def on_leave(self, event: events.Leave) -> None:
        """Resume auto-dismiss on un-hover."""
        if self.timer:
            self.timer.resume()


class ToastContainer(Vertical):
    """Container locked to the bottom-right corner to stack toasts."""

    DEFAULT_CSS = """
    ToastContainer {
        width: 45;
        height: auto;
        dock: right;
        align: right bottom;
        layer: overlay;
        background: transparent;
    }
    """

    def __init__(self) -> None:
        # Avoid stealing focus or pointer events when empty
        super().__init__(id="toast-container")
        self.styles.pointer_events = "none"

    def on_mount(self) -> None:
        # Watch children to toggle pointer events
        self.watch(self, "children", self._check_children)

    def _check_children(self, *args) -> None:
        if len(self.children) > 0:
            self.styles.pointer_events = "auto"
        else:
            self.styles.pointer_events = "none"


def notify(
    app: App,
    title: str,
    message: str = "",
    severity: Severity = "info",
    timeout: float = 4.0,
    action_label: Optional[str] = None,
    action_callback: Optional[Callable[[], Any]] = None,
) -> None:
    """
    Global helper to dispatch a toast notification.
    Expects `#toast-container` to exist in the app.
    """
    try:
        container = app.query_one("#toast-container", ToastContainer)

        # Enforce max 5 visible toasts limit
        if len(container.children) >= 5:
            container.children[0].remove()

        toast = Toast(
            ToastMessage(title, message, severity, timeout, action_label, action_callback)
        )
        container.mount(toast)
        logger.debug(f"Pushed toast notification: {title}")
    except Exception as e:
        logger.error(f"Failed to push toast '{title}': {e}")
