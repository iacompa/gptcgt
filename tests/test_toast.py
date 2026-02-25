import pytest
from textual.app import App, ComposeResult

from src.tui.widgets.toast import Toast, ToastContainer, notify


class MockApp(App):
    def compose(self) -> ComposeResult:
        yield ToastContainer()


@pytest.mark.asyncio
async def test_toast_container_mounts():
    app = MockApp()
    async with app.run_test():
        container = app.query_one(ToastContainer)
        assert container is not None
        assert len(container.children) == 0


@pytest.mark.asyncio
async def test_notify_pushes_toast():
    app = MockApp()
    async with app.run_test() as pilot:
        notify(app, "Test Info", "Hello World", severity="info")
        await pilot.pause()
        container = app.query_one(ToastContainer)

        toasts = container.query(Toast)
        assert len(toasts) == 1

        toast = toasts[0]
        assert toast.msg.title == "Test Info"
        assert toast.msg.message == "Hello World"
        assert toast.msg.severity == "info"
        assert "-info" in toast.classes


@pytest.mark.asyncio
async def test_toast_auto_dismisses():
    app = MockApp()
    async with app.run_test() as pilot:
        # Short timeout
        notify(app, "Timeout test", timeout=0.1)
        await pilot.pause()

        toasts = app.query(Toast)
        assert len(toasts) == 1

        # Wait for timeout AND animation (0.1 + 0.3)
        await pilot.pause(0.5)

        toasts = app.query(Toast)
        assert len(toasts) == 0
