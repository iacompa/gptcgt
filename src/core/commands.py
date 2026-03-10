"""
Central registry for all executable commands in the application.
Provides a single source of truth for shortcuts, slash commands, and palette actions.
"""

from __future__ import annotations

import difflib
import shlex
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from src.core.logger import get_logger

logger = get_logger("core.commands")


class CommandCategory(Enum):
    GLOBAL = "Global"
    FILE = "File"
    EDIT = "Edit"
    VIEW = "View"
    CHAT = "Chat"
    AI_TASKS = "AI Tasks"
    CODE_REVIEW = "Code Review"
    PREFERENCES = "Preferences"
    HELP = "Help"


@dataclass
class Command:
    """An executable action within the application."""

    id: str  # Unique identifier, e.g., 'app.quit'
    title: str  # Human-readable title, e.g., 'Quit Application'
    action: Callable[[], Any]  # The actual function to run
    shortcut: Optional[str] = None  # Textual shortcut string, e.g., 'ctrl+q'
    slash: Optional[str] = None  # Chat slash command, e.g., '/quit'
    description: str = ""  # Longer explainer
    category: CommandCategory = CommandCategory.GLOBAL  # Grouping for the command palette
    icon: str = ""  # Emoji or Nerd Font symbol
    enabled: bool = True  # Can the command be executed currently?
    visible: bool = True  # Should it appear in palettes/menus?
    requires_ai: bool = False  # Does it need the AI loop?


class CommandRegistry:
    """Singleton tracking all available commands."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._commands = {}
            cls._instance._by_shortcut = {}
            cls._instance._by_slash = {}
        return cls._instance

    def register(self, command: Command) -> None:
        """Register a new command."""
        self._commands[command.id] = command
        if command.shortcut:
            self._by_shortcut[command.shortcut] = command
        if command.slash:
            self._by_slash[command.slash] = command
        logger.debug(
            f"Registered command: {command.id} (shortcut: {command.shortcut}, slash: {command.slash})"  # noqa: E501
        )

    def unregister(self, command_id: str) -> None:
        """Remove a command."""
        if command_id in self._commands:
            cmd = self._commands[command_id]
            if cmd.shortcut and cmd.shortcut in self._by_shortcut:
                del self._by_shortcut[cmd.shortcut]
            if cmd.slash and cmd.slash in self._by_slash:
                del self._by_slash[cmd.slash]
            del self._commands[command_id]
            logger.debug(f"Unregistered command: {command_id}")

    def execute(self, identifier: str) -> bool:
        """
        Execute by ID, shortcut, or slash.
        Returns True if found and executed, else False.
        """
        cmd = self._commands.get(identifier) or self._by_shortcut.get(identifier) or self._by_slash.get(identifier)
        if cmd:
            if not cmd.enabled:
                logger.warning(f"Attempted to execute disabled command: {cmd.id}")
                return False

            try:
                logger.info(f"Executing command: {cmd.id}")
                cmd.action()
                return True
            except Exception as e:
                logger.error(f"Command execution failed {cmd.id}: {e}")
                return False
        logger.warning(f"Command not found: {identifier}")
        return False

    def resolve_slash(self, text: str) -> tuple[Command | None, list[str]]:
        """
        Parse a slash command string into (Command, args) using shlex.  # noqa: D213

        Returns (None, []) if the command is not found.
        """
        try:
            parts = shlex.split(text)
        except ValueError:
            parts = text.split()
        if not parts:
            return None, []
        base = parts[0].lower()
        args = parts[1:]
        cmd = self._by_slash.get(base)
        return cmd, args

    def get_slash_commands(self) -> list[Command]:
        """Return all registered slash commands (visible only)."""
        return [cmd for cmd in self._by_slash.values() if cmd.visible]

    def set_enabled(self, command_id: str, enabled: bool) -> None:
        """Toggle command execution ability."""
        if command_id in self._commands:
            self._commands[command_id].enabled = enabled

    def set_visible(self, command_id: str, visible: bool) -> None:
        """Toggle command visibility in palettes."""
        if command_id in self._commands:
            self._commands[command_id].visible = visible

    def get_by_category(self, category: CommandCategory) -> list[Command]:
        """Return visible commands in a specific category."""
        return [cmd for cmd in self._commands.values() if cmd.category == category and cmd.visible]

    def get_all(self) -> list[Command]:
        """Return all registered commands."""
        return list(self._commands.values())

    def search(self, query: str) -> list[Command]:
        """Fuzzy search across titles and descriptions using difflib for typo tolerance."""
        visible_cmds = [cmd for cmd in self._commands.values() if cmd.visible]
        if not query:
            return visible_cmds

        q = query.lower()

        # Exact slash command match
        if q.startswith("/"):
            if q in self._by_slash and self._by_slash[q].visible:
                return [self._by_slash[q]]
            return []

        results = []
        titles = [cmd.title for cmd in visible_cmds]

        # Find close matches for title
        close_titles = difflib.get_close_matches(query, titles, n=15, cutoff=0.3)

        for cmd in visible_cmds:
            score = 0
            t = cmd.title.lower()
            d = cmd.description.lower()

            if t == q:
                score = 100
            elif t.startswith(q):
                score = 80
            elif q in t:
                score = 60
            elif cmd.title in close_titles:
                score = 50 + close_titles.index(cmd.title) * -1
            elif q in d:
                score = 40

            if score > 0:
                results.append((score, cmd))

        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)
        return [cmd for score, cmd in results]


def register_default_commands(app: Any) -> None:
    """
    Hook to define and register the core application commands.
    Usually called during app.on_mount().
    """
    registry = CommandRegistry()

    # We clear it first, just in case this is called multiple times (e.g. testing)
    registry._commands.clear()
    registry._by_shortcut.clear()
    registry._by_slash.clear()

    # Panel toggles
    registry.register(
        Command(
            "view.toggle_left",
            "Toggle Left Panel (File Tree)",
            app.action_toggle_left_panel,
            shortcut="ctrl+b",
            category=CommandCategory.VIEW,
            icon="🗂️",
        )
    )
    registry.register(
        Command(
            "view.toggle_right",
            "Toggle Right Panel (Chat)",
            app.action_toggle_right_panel,
            shortcut="ctrl+j",
            category=CommandCategory.VIEW,
            icon="💬",
        )
    )
    registry.register(
        Command(
            "view.zen_mode",
            "Toggle Zen Mode",
            app.action_toggle_zen_mode,
            shortcut="ctrl+shift+z",
            slash="/zen",
            category=CommandCategory.VIEW,
            icon="🧘",
        )
    )
    registry.register(
        Command(
            "view.theme",
            "Toggle Theme (Light/Dark)",
            app.action_toggle_theme,
            shortcut="ctrl+t",
            slash="/theme",
            category=CommandCategory.VIEW,
            icon="🎨",
        )
    )

    # Search & Overlays
    registry.register(
        Command(
            "app.palette",
            "Show Command Palette",
            getattr(app, "action_command_palette", lambda: None),
            shortcut="ctrl+shift+p",
            category=CommandCategory.GLOBAL,
            icon="⚡",
        )
    )
    registry.register(
        Command(
            "app.fuzzy_search",
            "Quick Open File",
            getattr(app, "action_fuzzy_search", lambda: None),
            shortcut="ctrl+p",
            category=CommandCategory.GLOBAL,
            icon="🔍",
        )
    )

    # Configuration
    registry.register(
        Command(
            "app.settings",
            "Open Settings",
            getattr(app, "action_show_settings", lambda: None),
            shortcut="ctrl+comma",
            slash="/settings",
            category=CommandCategory.PREFERENCES,
            icon="⚙️",
        )
    )
    registry.register(
        Command(
            "app.tiers",
            "Select Quality Tier",
            getattr(app, "action_tier_selector", lambda: None),
            shortcut="ctrl+q",
            slash="/tier",
            category=CommandCategory.PREFERENCES,
            icon="💎",
        )
    )
    registry.register(
        Command(
            "app.history",
            "Session History",
            getattr(app, "action_session_history", lambda: None),
            shortcut="ctrl+h",
            slash="/history",
            category=CommandCategory.CHAT,
            icon="📜",
        )
    )
    registry.register(
        Command(
            "app.help",
            "Show Help",
            getattr(app, "action_show_help", lambda: None),
            shortcut="ctrl+question_mark",
            slash="/help",
            category=CommandCategory.HELP,
            icon="❓",
        )
    )

    # App state
    registry.register(
        Command(
            "app.quit",
            "Quit Application",
            getattr(app, "exit", lambda: None),
            slash="/quit",
            category=CommandCategory.GLOBAL,
            icon="🚪",
        )
    )
    registry.register(
        Command(
            "chat.clear",
            "Clear Chat",
            getattr(app, "action_clear_chat", lambda: None),
            slash="/clear",
            category=CommandCategory.CHAT,
            icon="🧹",
        )
    )

    registry.register(
        Command(
            id="app.status",
            title="Provider Status",
            action=getattr(app, "action_show_status", lambda: None),
            slash="/status",
            category=CommandCategory.HELP,
            icon="📊",
        )
    )
    registry.register(
        Command(
            id="app.version",
            title="Show Version",
            action=getattr(app, "action_show_version", lambda: None),
            slash="/version",
            category=CommandCategory.HELP,
            icon="🔖",
        )
    )
    registry.register(
        Command(
            id="auth.login",
            title="Sign In",
            action=getattr(app, "action_login", lambda: None),
            slash="/login",
            category=CommandCategory.PREFERENCES,
            icon="🔑",
        )
    )
    registry.register(
        Command(
            id="auth.logout",
            title="Sign Out",
            action=getattr(app, "action_logout", lambda: None),
            slash="/logout",
            category=CommandCategory.PREFERENCES,
            icon="🚪",
        )
    )
    registry.register(
        Command(
            id="billing.credits",
            title="Check Credits",
            action=getattr(app, "action_show_credits", lambda: None),
            slash="/credits",
            category=CommandCategory.PREFERENCES,
            icon="💰",
        )
    )
    registry.register(
        Command(
            id="billing.billing",
            title="Billing Info",
            action=getattr(app, "action_show_billing", lambda: None),
            slash="/billing",
            category=CommandCategory.PREFERENCES,
            icon="💳",
        )
    )

    # Optional handler if mock app lacks chat_store
    def new_session_action():
        return None

    if hasattr(app, "chat_store"):

        def new_session_action():  # noqa: F811
            app.chat_store.new_session()
            # Immediately reload chat panel so user sees the reset
            try:
                from src.tui.panels.chat import ChatPanel

                chat_panel = app.query_one("#right-panel", ChatPanel)
                chat_panel._load_session_history()
            except Exception:
                pass

    registry.register(
        Command(
            "chat.new",
            "New Session",
            new_session_action,
            slash="/new",
            category=CommandCategory.CHAT,
            icon="✨",
            description="Start a fresh chat session.",
        )
    )

    # ── New argument-aware slash commands ──────────────────
    # These are registered as no-op actions; actual logic is in ChatPanel._handle_slash_command
    # because they need access to the chat panel and/or take arguments.
    registry.register(
        Command(
            id="chat.export",
            title="Export Session",
            action=lambda: None,  # handled by ChatPanel
            slash="/export",
            category=CommandCategory.CHAT,
            icon="📤",
            description="Export current session as timestamped markdown file.",
        )
    )
    registry.register(
        Command(
            id="chat.compact",
            title="Compact Context",
            action=lambda: None,
            slash="/compact",
            category=CommandCategory.CHAT,
            icon="📦",
            description="Summarize older messages to reclaim context window.",
        )
    )
    registry.register(
        Command(
            id="chat.cost",
            title="Cost Summary",
            action=lambda: None,
            slash="/cost",
            category=CommandCategory.CHAT,
            icon="💰",
            description="Show session/daily/monthly cost breakdown.",
        )
    )
    registry.register(
        Command(
            id="chat.context",
            title="Context Budget",
            action=lambda: None,
            slash="/context",
            category=CommandCategory.CHAT,
            icon="📊",
            description="Show current context window usage stats.",
        )
    )
    registry.register(
        Command(
            id="chat.mode",
            title="Switch Mode",
            action=lambda: None,
            slash="/mode",
            category=CommandCategory.CHAT,
            icon="🎯",
            description="Switch mode: /mode scout|standard|ensemble|battle|architect.",
        )
    )
    registry.register(
        Command(
            id="chat.auto",
            title="Autonomous Mode",
            action=lambda: None,
            slash="/auto",
            category=CommandCategory.CHAT,
            icon="🚀",
            description="Start autonomous mode: /auto <goal>. AI agents collaborate to build your project.",
        )
    )

    # Additional commands for menu alignment
    registry.register(
        Command(
            "file.new",
            "New File",
            lambda: None,
            shortcut="ctrl+n",
            category=CommandCategory.FILE,
            icon="📄",
        )
    )
    registry.register(
        Command(
            "file.save",
            "Save",
            lambda: None,
            shortcut="ctrl+s",
            category=CommandCategory.FILE,
            icon="💾",
        )
    )
    registry.register(
        Command(
            "edit.undo",
            "Undo",
            lambda: None,
            shortcut="ctrl+z",
            category=CommandCategory.EDIT,
            icon="↩️",
        )
    )
    registry.register(
        Command(
            "edit.redo",
            "Redo",
            lambda: None,
            shortcut="ctrl+y",
            category=CommandCategory.EDIT,
            icon="↪️",
        )
    )
