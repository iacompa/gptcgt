from __future__ import annotations

from textual.app import App
from textual.events import MouseDown

from src.tui.widgets.menu import DropdownMenu, MenuItem


class ContextMenuSpawner:
    """Helper to spawn context menus at mouse locations."""

    @staticmethod
    def spawn(app: App, event: MouseDown, items: list[MenuItem]) -> None:
        """Spawns a DropdownMenu at the mouse coordinates."""
        # Find existing dropdowns and close them
        for existing in app.screen.query(DropdownMenu):
            existing.close_all()

        menu = DropdownMenu(items, x=event.screen_x, y=event.screen_y)
        app.screen.mount(menu)
