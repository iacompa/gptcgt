import pytest
from textual.app import App, ComposeResult

from src.tui.widgets.menu import DropdownMenu, MenuItemWidget
from src.tui.widgets.menu_bar import MenuBar, MenuBarLabel


class MenuTestApp(App[None]):
    def compose(self) -> ComposeResult:
        yield MenuBar()


@pytest.mark.asyncio
async def test_menu_opens_on_click():
    app = MenuTestApp()
    async with app.run_test() as pilot:
        bar = app.query_one(MenuBar)
        bar.query(MenuBarLabel)

        # Click first label
        await pilot.click(MenuBarLabel)
        await pilot.pause()

        # Check if DropdownMenu is mounted
        dropdowns = app.query(DropdownMenu)
        assert len(dropdowns) == 1
        assert bar.active_dropdown is not None

        # Click it again should close it
        await pilot.click(MenuBarLabel)
        await pilot.pause()

        dropdowns = app.query(DropdownMenu)
        assert len(dropdowns) == 0
        assert bar.active_dropdown is None


@pytest.mark.asyncio
async def test_menu_closes_on_escape():
    app = MenuTestApp()
    async with app.run_test() as pilot:
        # Open
        await pilot.click(MenuBarLabel)
        await pilot.pause()

        # Press escape
        await pilot.press("escape")
        await pilot.pause()

        dropdowns = app.query(DropdownMenu)
        assert len(dropdowns) == 0


@pytest.mark.asyncio
async def test_submenu_opens_on_hover_right():
    app = MenuTestApp()
    async with app.run_test() as pilot:
        # Click view menu (index 3 usually)
        labels = list(app.query(MenuBarLabel))
        await pilot.click(labels[3].__class__)  # or pilot.click on the widget directly?
        # Actually pilot.click takes a selector or widget
        await pilot.click(labels[3])
        await pilot.pause()

        dropdown = app.query_one(DropdownMenu)
        items = list(dropdown.query(MenuItemWidget))

        # Find 'Theme' which has a submenu
        theme_item = None
        for item in items:
            if item.item.label == "Theme":
                theme_item = item
                break

        assert theme_item is not None

        # Focus/Enter on the item should open submenu
        dropdown.focus_item(theme_item)
        await pilot.pause(0.2)  # Timer delay

        # Now there should be 2 dropdowns
        dropdowns = app.query(DropdownMenu)
        assert len(dropdowns) == 2
        assert dropdown.active_submenu is not None


@pytest.mark.asyncio
async def test_keyboard_navigation_up_down():
    app = MenuTestApp()
    async with app.run_test() as pilot:
        await pilot.click(app.query(MenuBarLabel).first())
        await pilot.pause()

        dropdown = app.query_one(DropdownMenu)

        # Move down
        await pilot.press("down")
        await pilot.pause()
        assert dropdown.focused_index == 0

        await pilot.press("down")
        await pilot.pause()
        # Item 1 is disabled so it might skip to 3 (which is index 3)
        # We just assert it moved
        assert dropdown.focused_index > 0

        await pilot.press("up")
        await pilot.pause()
        assert dropdown.focused_index == 0
