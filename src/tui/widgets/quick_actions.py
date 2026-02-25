"""
Quick actions bar for common contextual workflows.

Displays a horizontal list of buttons driven by the current context
(e.g., active file, code selection). Pressing a button emits a
QuickActionTriggered event.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static

from src.core.events import QuickActionTriggered
from src.core.logger import get_logger

logger = get_logger("tui.quick_actions")


class QuickActionButton(Button):
    """A button representing a specific contextual action."""

    def __init__(self, label: str, action: str, **kwargs) -> None:
        super().__init__(label, **kwargs)
        self.action_name = action


class QuickActionsBar(Horizontal):
    """
    Container for contextual quick actions, toggled via Ctrl+Space.

    Its context property takes a dict describing the current TUI state
    (e.g., {"target": "file", "file_path": "..."}, or {"target": "selection", ...}).
    Updating the context automatically updates the displayed buttons.
    """

    DEFAULT_CSS = """
    QuickActionsBar {
        height: 3;
        width: 100%;
        background: $surface;
        border-top: solid $secondary;
        align: left middle;
        padding: 0 1;
        display: none;
    }
    QuickActionsBar.visible {
        display: block;
    }
    .qa-label {
        color: $text-muted;
        margin-right: 2;
    }
    QuickActionButton {
        height: 1;
        border: none;
        background: $panel;
        color: $text;
        margin-right: 1;
        min-width: 12;
    }
    QuickActionButton:hover {
        background: $primary;
        color: $background;
    }
    QuickActionButton.-active {
        background: $secondary;
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._qa_context: dict | None = None
        # Default actions when no specific context is active
        self._default_actions = [
            ("💡 Explain Project", "explain_project"),
            ("🐛 Find Bugs", "find_bugs"),
            ("🧪 Write Tests", "write_tests"),
        ]

    @property
    def context(self) -> dict | None:
        return self._qa_context

    @context.setter
    def context(self, new_context: dict | None) -> None:
        self._qa_context = new_context
        self._refresh_buttons()

    def compose(self) -> ComposeResult:
        yield Static("⚡ Actions  [dim]Ctrl+Space[/dim]:", classes="qa-label")
        # Mount default buttons initially
        for label, action in self._default_actions:
            yield QuickActionButton(label, action)

    def _refresh_buttons(self) -> None:
        """Update the displayed buttons based on the current context."""
        # Remove existing buttons
        for btn in self.query(QuickActionButton):
            btn.remove()

        actions = self._build_actions_for_context()
        for label, action in actions:
            self.mount(QuickActionButton(label, action))

    def _build_actions_for_context(self) -> list[tuple[str, str]]:
        """Determine appropriate actions based on context."""
        if not self._qa_context:
            return self._default_actions

        target = self._qa_context.get("target")

        if target == "selection":
            return [
                ("💡 Explain Selection", "explain_selection"),
                ("🐛 Find Bugs", "find_bugs_selection"),
                ("♻️ Refactor", "refactor_selection"),
                ("🧪 Write Tests", "write_tests_selection"),
                ("🔒 Security Scan", "security_scan_selection"),
            ]
        elif target == "file":
            return [
                ("💡 Explain File", "explain_file"),
                ("🐛 Find Bugs", "find_bugs_file"),
                ("♻️ Refactor File", "refactor_file"),
                ("🧪 Write Tests", "write_tests_file"),
                ("🔒 Security Scan", "security_scan_file"),
            ]
        else:
            return self._default_actions

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks and emit QuickActionTriggered."""
        if isinstance(event.button, QuickActionButton):
            action = event.button.action_name
            logger.info(f"Quick action triggered: {action}")
            # Brief loading feedback on button
            orig_label = str(event.button.label)
            event.button.label = "🔄 Running..."
            event.button.add_class("-active")
            self.set_timer(1.5, lambda: self._restore_button(event.button, orig_label))
            # Hide the bar after clicking an action
            self.remove_class("visible")
            self.post_message(
                QuickActionTriggered(
                    action=action,
                    context=self._qa_context or {},
                )
            )

    def _restore_button(self, btn: Button, orig_label: str) -> None:
        """Reset button label after action fires."""
        try:
            btn.label = orig_label
            btn.remove_class("-active")
        except Exception:
            pass

    def toggle_visibility(self) -> None:
        """Show or hide the quick actions bar."""
        if self.has_class("visible"):
            self.remove_class("visible")
        else:
            self.add_class("visible")
