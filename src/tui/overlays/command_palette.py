from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option

from src.core.commands import Command, CommandCategory, CommandRegistry
from src.core.logger import get_logger

logger = get_logger("tui.palette")


class CommandPaletteScreen(ModalScreen[None]):
    """
    A VS Code style fuzzy-search command palette.
    Pressing Ctrl+Shift+P opens this.
    """

    DEFAULT_CSS = """
    CommandPaletteScreen {
        align: center middle;
        background: $background 50%;
    }

    #palette-container {
        width: 60;
        height: 60%;
        background: $panel;
        border: thick $primary;
    }

    #palette-input {
        dock: top;
        margin: 1;
        width: 100%;
        border: none;
        border-bottom: solid $primary-muted;
    }

    #palette-list {
        height: 100%;
        border: none;
        background: transparent;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.registry = CommandRegistry()
        self.commands: list[Command] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-container"):
            yield Input(placeholder="Type a command...", id="palette-input")
            yield OptionList(id="palette-list")

    def on_mount(self) -> None:
        self.query_one("#palette-input").focus()
        self._refresh_list("")

    def on_input_changed(self, event: Input.Changed) -> None:
        self._refresh_list(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        list_widget = self.query_one("#palette-list", OptionList)
        if list_widget.highlighted is not None and self._valid_indices:
            self._execute_highlighted(list_widget.highlighted)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_index is not None and self._valid_indices:
            self._execute_highlighted(event.option_index)

    def _refresh_list(self, query: str) -> None:
        """Update the OptionList based on the query."""
        list_widget = self.query_one("#palette-list", OptionList)
        list_widget.clear_options()

        raw_commands = self.registry.search(query)
        self.commands = []
        self._valid_indices = {}  # Maps option index -> command index

        options = []
        current_option_idx = 0

        if not query:
            # Group by category
            from collections import defaultdict

            groups = defaultdict(list)
            for cmd in raw_commands:
                groups[cmd.category].append(cmd)

            for cat in CommandCategory:
                if cat in groups:
                    # Add unselectable header
                    header = Text(f"--- {cat.value} ---", style="bold cyan")
                    options.append(Option(header, disabled=True))
                    current_option_idx += 1

                    for cmd in groups[cat]:
                        self.commands.append(cmd)
                        options.append(self._build_option(cmd))
                        self._valid_indices[current_option_idx] = len(self.commands) - 1
                        current_option_idx += 1
        else:
            # Sorted by relevance purely
            for cmd in raw_commands:
                self.commands.append(cmd)
                options.append(self._build_option(cmd))
                self._valid_indices[current_option_idx] = len(self.commands) - 1
                current_option_idx += 1

        if options:
            list_widget.add_options(options)
        else:
            list_widget.add_option(Option("No commands found", disabled=True))

    def _build_option(self, cmd: Command) -> Option:
        """Construct the Rich text formatting for a command option."""
        label = Text()
        style = "dim" if not cmd.enabled else ""

        if cmd.icon:
            label.append(f"{cmd.icon} ", style=style)

        label.append(f"[{cmd.category.value}] ", style="blue" if cmd.enabled else "dim")
        label.append(cmd.title, style=style)

        if cmd.shortcut:
            label.append(f"  ({cmd.shortcut})", style="italic " + style)
        if cmd.slash:
            label.append(f"  {cmd.slash}", style="green" if cmd.enabled else "dim")

        return Option(label, id=cmd.id, disabled=not cmd.enabled)

    def _execute_highlighted(self, index: int) -> None:
        if index in self._valid_indices:
            cmd = self.commands[self._valid_indices[index]]
            if cmd.enabled:
                logger.info(f"Command palette executed: {cmd.id}")
                self.dismiss()
                self.app.call_after_refresh(cmd.action)
