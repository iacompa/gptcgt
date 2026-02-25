import pytest
from textual.app import App, ComposeResult
from textual.events import MouseDown

from src.tui.panels.chat import ChatPanel
from src.tui.panels.code_viewer import CodeViewerPanel
from src.tui.panels.file_tree import FileTreePanel
from src.tui.widgets.menu import DropdownMenu


class ContextTestApp(App[None]):
    def compose(self) -> ComposeResult:
        yield FileTreePanel()
        yield CodeViewerPanel()
        yield ChatPanel()


@pytest.mark.asyncio
async def test_file_tree_context_menu():
    app = ContextTestApp()
    async with app.run_test(size=(100, 50)) as pilot:
        await pilot.pause()

        tree = app.query_one(FileTreePanel)

        # Right click on tree
        event = MouseDown(
            tree,
            x=0,
            y=0,
            delta_x=0,
            delta_y=0,
            button=3,
            shift=False,
            meta=False,
            ctrl=False,
            screen_x=10,
            screen_y=10,
        )
        tree.post_message(event)
        await pilot.pause()

        # Verify menu opened
        menus = app.query(DropdownMenu)
        assert len(menus) == 1
        assert any(item.item.label == "Rename" for item in menus.first()._item_widgets)

        # Close
        menus.first().close_all()
        await pilot.pause()


@pytest.mark.asyncio
async def test_chat_panel_context_menu():
    app = ContextTestApp()
    # Need to mock the active session loading or keychain check
    # ChatPanel does some stuff on submit, but mount should be fine
    async with app.run_test(size=(100, 50)) as pilot:
        await pilot.pause()

        chat = app.query_one(ChatPanel)
        event = MouseDown(
            chat,
            x=0,
            y=0,
            delta_x=0,
            delta_y=0,
            button=3,
            shift=False,
            meta=False,
            ctrl=False,
            screen_x=10,
            screen_y=10,
        )
        chat.post_message(event)
        await pilot.pause()

        menus = app.query(DropdownMenu)
        assert len(menus) == 1
        assert any(item.item.label == "Pin Session" for item in menus.first()._item_widgets)
