from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label


class HelpOverlay(ModalScreen):
    """Searchable help screen for all shortcuts and slash commands."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    HelpOverlay {
        align: center middle;
        background: $background 80%;
    }
    #help-dialog {
        width: 70;
        height: 35;
        background: $panel;
        border: solid $primary;
        padding: 1 2;
    }
    #help-search {
        margin-bottom: 1;
        background: $background;
        border: solid $secondary;
    }
    .help-section {
        color: $text;
        text-style: bold;
        margin-top: 1;
        border-bottom: solid $secondary;
    }
    .help-item {
        height: 1;
        margin-bottom: 0;
    }
    .help-key {
        width: 25;
        color: #4ADE80;
    }
    .help-desc {
        width: 1fr;
        color: $text-muted;
    }
    """

    SHORTCUTS = [
        ("Navigation", "Ctrl+P", "Search files"),
        ("Navigation", "Ctrl+B", "Toggle file tree panel"),
        ("Navigation", "Ctrl+J", "Toggle chat panel"),
        ("Navigation", "Ctrl+Shift+Z", "Zen mode (center panel only)"),
        ("Navigation", "Ctrl+\\", "Split center panel"),
        ("Navigation", "Tab", "Cycle panel focus"),
        ("Navigation", "Ctrl+G", "Go to line number"),
        ("AI & Tasks", "Ctrl+Enter", "Send message to AI"),
        ("AI & Tasks", "Ctrl+Q", "Change quality tier (Light/Standard/Max)"),
        ("AI & Tasks", "Ctrl+M", "Change operation mode"),
        ("AI & Tasks", "Ctrl+Shift+H", "Task history"),
        ("AI & Tasks", "@filename", "Reference a file in your message"),
        ("Code Review", "n / N", "Next / previous diff hunk"),
        ("Code Review", "Enter", "Approve current hunk"),
        ("Code Review", "a", "Approve all hunks"),
        ("Code Review", "r", "Reject all changes"),
        ("Settings", "Ctrl+,", "Open settings"),
        ("Settings", "Ctrl+T", "Cycle themes"),
        ("Settings", "Ctrl+? / F1", "This help screen"),
        ("Slash Commands", "/help", "Show this help"),
        ("Slash Commands", "/setup", "Re-run onboarding wizard"),
        ("Slash Commands", "/clear", "Clear chat display"),
        ("Slash Commands", "/status", "Check AI provider health"),
        ("Slash Commands", "/version", "Show application version"),
        ("Slash Commands", "/login", "Sign in for managed credits"),
        ("Slash Commands", "/logout", "Sign out of account"),
        ("Slash Commands", "/credits", "Check remaining managed credits"),
        ("Slash Commands", "/billing", "Manage your subscription"),
        ("Slash Commands", "/mode X", "Switch mode (scout/standard/ensemble/architect)"),
        ("Slash Commands", "/tier X", "Switch tier (light/standard/max)"),
        ("Slash Commands", "/cost", "Show today's cost summary"),
        ("Slash Commands", "/history", "Show task history"),
        ("Slash Commands", "/compact", "Compact AI context window"),
        ("Slash Commands", "/context", "Show context usage breakdown"),
        ("Slash Commands", "/export", "Export chat as markdown"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield Input(placeholder="Search shortcuts...", id="help-search")
            self.list_container = Vertical(id="help-list")
            yield self.list_container
            yield Label("\n[Press Esc to close]", classes="text-center text-secondary")

    def on_mount(self) -> None:
        self._populate_list()
        self.query_one("#help-search").focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._populate_list(event.value.lower())

    def _populate_list(self, filter_text: str = "") -> None:
        self.list_container.remove_children()

        current_section = None
        for section, key, desc in self.SHORTCUTS:
            if (
                filter_text
                and filter_text not in key.lower()
                and filter_text not in desc.lower()
                and filter_text not in section.lower()
            ):
                continue

            if section != current_section:
                self.list_container.mount(Label(f"─── {section} ───", classes="help-section"))
                current_section = section

            h = Horizontal(classes="help-item")
            h.mount(Label(key, classes="help-key"))
            h.mount(Label(desc, classes="help-desc"))
            self.list_container.mount(h)
