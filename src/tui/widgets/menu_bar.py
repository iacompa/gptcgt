from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Click
from textual.widgets import Label

from src.core.logger import get_logger
from src.tui.widgets.menu import DropdownMenu, MenuItem

logger = get_logger("tui.menu_bar")


class MenuBarLabel(Label):
    """A clickable label in the top menu bar."""

    DEFAULT_CSS = """
    MenuBarLabel {
        padding: 0 1;
        background: transparent;
        color: $text;
        text-style: bold;
        height: auto;
        min-height: 1;
        margin-right: 1;
    }
    MenuBarLabel:hover {
        background: transparent;
        color: $primary;
    }
    MenuBarLabel.-active {
        background: transparent;
        color: $primary;
        text-style: bold;
    }
    """

    def __init__(self, text: str, menu_items: list[MenuItem], parent_bar: "MenuBar") -> None:
        super().__init__(text)
        self.menu_items = menu_items
        self.parent_bar = parent_bar
        self.active_menu: DropdownMenu | None = None

    def on_click(self, event: Click) -> None:
        event.stop()
        self.parent_bar.toggle_menu(self)


class MenuBar(Horizontal):
    """The main top navigation bar."""

    DEFAULT_CSS = """
    MenuBar {
        height: auto;
        min-height: 1;
        width: 100%;
        background: $surface;
        dock: top;
        align: left middle;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.active_label: MenuBarLabel | None = None
        self.active_dropdown: DropdownMenu | None = None
        self.menus: dict[str, list[MenuItem]] = {}

    def compose(self) -> ComposeResult:
        self.menus = self._build_menus()

        for name, items in self.menus.items():
            yield MenuBarLabel(name, items, self)

    def _build_menus(self) -> dict[str, list[MenuItem]]:
        # This will be dynamically populated/updated or static based on app state
        # In a real app we'd inject dependencies or use app state

        # Match exact brand colors from AnimatedWelcome in chat.py
        gptcgt_colored = "[#34D399]gpt[/#34D399][#FB923C]c[/#FB923C][#60A5FA]g[/#60A5FA][#A78BFA]t[/#A78BFA]"

        gptcgt_menu = [
            MenuItem(f"About {gptcgt_colored}", action="about"),
            MenuItem("Check for Updates", action="check_updates"),
            MenuItem(is_separator=True),
            MenuItem("Preferences...", action="app.settings", shortcut="⌃,"),
            MenuItem(is_separator=True),
            MenuItem("Quit", action="app.quit", shortcut="⌃C"),
        ]

        task_menu = [
            MenuItem("New Session", action="chat.new"),
            MenuItem("Continue Last Session", action="continue_session"),
            MenuItem(is_separator=True),
            MenuItem("Task History", action="app.history", shortcut="⌃⇧H"),
            MenuItem(is_separator=True),
            MenuItem("Export Chat as Markdown", action="export_chat"),
            MenuItem("Clear Chat", action="chat.clear"),
            MenuItem(is_separator=True),
            MenuItem("Re-run Setup Wizard", action="push_onboarding"),
        ]

        agents_menu = [
            MenuItem(
                "Quality Tier",
                submenu=[
                    MenuItem("💡 Light  (cheapest)", action="tier_light"),
                    MenuItem("⚡ Standard  (recommended)", action="tier_standard"),
                    MenuItem("🔥 Max  (best quality)", action="tier_max"),
                ],
            ),
            MenuItem(
                "Operation Mode",
                submenu=[
                    MenuItem("🤖 Standard  (5 cr)  — best AI for task", action="mode_standard"),
                    MenuItem("🔍 Scout  (1 cr)  — fast analysis, no code", action="mode_scout"),
                    MenuItem("🚀 Ensemble  (25 cr)  — 3 AIs vote", action="mode_ensemble"),
                    MenuItem("⚔️ Battle  (25 cr)  — 2 AIs compete", action="mode_battle"),
                    MenuItem("🏗️ Architect  (100 cr)  — plan then build", action="mode_architect"),
                    MenuItem(is_separator=True),
                    MenuItem("⚙️ Full Mode Picker...   ⎵+M", action="mode_picker"),
                ],
            ),
            MenuItem(is_separator=True),
            MenuItem("Manage API Keys...", action="show_settings_keys", shortcut="⌃,"),
        ]

        view_menu = [
            MenuItem("Toggle File Tree", action="view.toggle_left", shortcut="⌃B"),
            MenuItem("Toggle Chat Panel", action="view.toggle_right", shortcut="⌃J"),
            MenuItem("Zen Mode", action="view.zen_mode", shortcut="⌃⇧Z"),
            MenuItem(is_separator=True),
            MenuItem(
                "Layout",
                submenu=[
                    MenuItem("Layout Editor...", action="show_layout_editor", shortcut="⌃L"),
                    MenuItem(is_separator=True),
                    MenuItem("Default (Tree|Code|Chat)", action="layout_default"),
                    MenuItem("Code Focus (Code|Chat)", action="layout_code_focus"),
                    MenuItem("Review (Tree|Code)", action="layout_review"),
                    MenuItem("Chat Focus (Tree|Chat)", action="layout_chat_focus"),
                ],
            ),
            MenuItem(
                "Panel Sizes",
                submenu=[
                    MenuItem("Default (20/50/30)", action="size_default"),
                    MenuItem("Wide Code (15/60/25)", action="size_wide_code"),
                    MenuItem("Wide Chat (15/40/45)", action="size_wide_chat"),
                    MenuItem("Equal (33/34/33)", action="size_equal"),
                ],
            ),
            MenuItem(is_separator=True),
            MenuItem(
                "Theme",
                submenu=[
                    MenuItem("🌙 Midnight", action="theme_midnight"),
                    MenuItem("☀️ Polar", action="theme_polar"),
                    MenuItem("🌊 Slate", action="theme_slate"),
                    MenuItem("🔥 Ember", action="theme_ember"),
                    MenuItem("⚡ Neon", action="theme_neon"),
                ],
            ),
        ]

        settings_menu = [
            MenuItem("API Keys...", action="show_settings_keys", shortcut="⌃,"),
            MenuItem(is_separator=True),
            MenuItem(
                "Privacy & Security",
                submenu=[
                    MenuItem("Auto security scan", is_toggle=True, toggle_state=True),
                    MenuItem("Confirm before applying", is_toggle=True, toggle_state=True),
                    MenuItem("Store chat on disk", is_toggle=True, toggle_state=True),
                ],
            ),
            MenuItem(is_separator=True),
            MenuItem("Billing Overlay...", action="show_billing"),
        ]

        help_menu = [
            MenuItem("Keyboard Shortcuts", action="app.help", shortcut="⌃?/F1"),
            MenuItem(is_separator=True),
            MenuItem("Documentation", action="open_docs"),
            MenuItem("Getting Started Guide", action="open_guide"),
            MenuItem(is_separator=True),
            MenuItem("Report an Issue", action="open_issues"),
        ]

        return {
            gptcgt_colored: gptcgt_menu,
            "Task": task_menu,
            "Agents": agents_menu,
            "View": view_menu,
            "Settings": settings_menu,
            "Help": help_menu,
        }

    def toggle_menu(self, label_widget: MenuBarLabel) -> None:
        # If clicking the currently open label, close it
        if self.active_label == label_widget and self.active_dropdown:
            self.close_all()
            return

        self.close_all()
        logger.debug(f"Opening menu dropdown: {label_widget.render()}")

        # Calculate position explicitly via global regions (0 offset horizontally starting from label)  # noqa: E501
        # Using Region to find true terminal coordinates
        region = label_widget.region
        x = region.x
        y = region.y + region.height

        self.active_label = label_widget
        self.active_label.add_class("-active")

        self.active_dropdown = DropdownMenu(label_widget.menu_items, x=x, y=y)
        self.screen.mount(self.active_dropdown)

    def close_all(self) -> None:
        if self.active_dropdown:
            self.active_dropdown.close_all()
            self.active_dropdown = None
        if self.active_label:
            self.active_label.remove_class("-active")
            self.active_label = None
