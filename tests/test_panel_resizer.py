import pytest
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.events import MouseDown, MouseMove, MouseUp
from textual.widgets import Static

from src.tui.widgets.panel_resizer import PanelResizer


class ResizerApp(App[None]):
    CSS = """
    #left-panel { width: 20; min-width: 15; }
    #right-panel { width: 1fr; min-width: 20; }
    """

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("Left", id="left-panel")
            yield PanelResizer("left-panel", "right-panel", id="resizer")
            yield Static("Right", id="right-panel")


@pytest.mark.asyncio
async def test_panel_resizer_drag():
    app = ResizerApp()
    async with app.run_test(size=(100, 20)) as pilot:
        left = app.query_one("#left-panel")
        right = app.query_one("#right-panel")
        resizer = app.query_one("#resizer", PanelResizer)

        # Initial widths
        assert left.outer_size.width == 20
        # Right gets the rest, so around 79 (1 for resizer)
        assert right.outer_size.width == 79

        # Simulate MouseDown
        # In text environment, we just send a MouseDown event directly
        down_event = MouseDown(
            resizer,
            x=0,
            y=0,
            delta_x=0,
            delta_y=0,
            button=1,
            shift=False,
            meta=False,
            ctrl=False,
            screen_x=20,
            screen_y=10,
        )
        resizer.post_message(down_event)
        await pilot.pause()

        assert resizer._dragging is True

        # We manually dispatch MouseMove since pilot doesn't do drag well
        move_event = MouseMove(
            resizer,
            x=0,
            y=0,
            delta_x=10,
            delta_y=0,
            button=1,
            shift=False,
            meta=False,
            ctrl=False,
            screen_x=30,
            screen_y=10,
        )
        resizer.post_message(move_event)
        await pilot.pause()

        # Left should be 20 + 10 = 30
        assert left.styles.width.value == 30.0
        # Right should be 79 - 10 = 69
        assert right.styles.width.value == 69.0

        # MouseUp
        up_event = MouseUp(
            resizer,
            x=0,
            y=0,
            delta_x=0,
            delta_y=0,
            button=1,
            shift=False,
            meta=False,
            ctrl=False,
            screen_x=30,
            screen_y=10,
        )
        resizer.post_message(up_event)
        await pilot.pause()

        assert resizer._dragging is False


@pytest.mark.asyncio
async def test_panel_resizer_double_click_reset():
    app = ResizerApp()

    messages = []

    class TestResizer(PanelResizer):
        def on_panel_resizer_reset_layout(self, event):
            messages.append("ResetLayout")

    # We monkeypatch the app to use TestResizer to capture the message easier
    # Or actually the message bubbles up
    app.query_one = lambda selector, *args, **kwargs: app.screen.query_one(
        selector, *args, **kwargs
    )

    async with app.run_test(size=(100, 20)) as pilot:
        resizer = app.query_one("#resizer", PanelResizer)

        # Double click simulation
        down_event1 = MouseDown(
            resizer,
            x=0,
            y=0,
            delta_x=0,
            delta_y=0,
            button=1,
            shift=False,
            meta=False,
            ctrl=False,
            screen_x=20,
            screen_y=10,
        )
        resizer.post_message(down_event1)
        up_event1 = MouseUp(
            resizer,
            x=0,
            y=0,
            delta_x=0,
            delta_y=0,
            button=1,
            shift=False,
            meta=False,
            ctrl=False,
            screen_x=20,
            screen_y=10,
        )
        resizer.post_message(up_event1)

        down_event2 = MouseDown(
            resizer,
            x=0,
            y=0,
            delta_x=0,
            delta_y=0,
            button=1,
            shift=False,
            meta=False,
            ctrl=False,
            screen_x=20,
            screen_y=10,
        )
        resizer.post_message(down_event2)
        up_event2 = MouseUp(
            resizer,
            x=0,
            y=0,
            delta_x=0,
            delta_y=0,
            button=1,
            shift=False,
            meta=False,
            ctrl=False,
            screen_x=20,
            screen_y=10,
        )
        resizer.post_message(up_event2)

        await pilot.pause()

        # We check if the app received the message. The app doesn't implement a handler,
        # but the event should be posted.
        assert resizer._click_count == 0  # Reset after double click


@pytest.mark.asyncio
async def test_panel_resizer_uses_screen_position_when_delta_is_zero():
    """Regression: some terminals report delta_x=0 during a drag move."""
    app = ResizerApp()
    async with app.run_test(size=(100, 20)) as pilot:
        left = app.query_one("#left-panel")
        right = app.query_one("#right-panel")
        resizer = app.query_one("#resizer", PanelResizer)

        assert left.outer_size.width == 20
        assert right.outer_size.width == 79

        down_event = MouseDown(
            resizer,
            x=0,
            y=0,
            delta_x=0,
            delta_y=0,
            button=1,
            shift=False,
            meta=False,
            ctrl=False,
            screen_x=20,
            screen_y=10,
        )
        resizer.post_message(down_event)
        await pilot.pause()

        # delta_x intentionally 0 while screen_x moves right by +8
        move_event = MouseMove(
            resizer,
            x=0,
            y=0,
            delta_x=0,
            delta_y=0,
            button=1,
            shift=False,
            meta=False,
            ctrl=False,
            screen_x=28,
            screen_y=10,
        )
        resizer.post_message(move_event)
        await pilot.pause()

        assert left.styles.width.value == 28.0
        assert right.styles.width.value == 71.0
