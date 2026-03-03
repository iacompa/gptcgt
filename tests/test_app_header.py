import pytest  # noqa: I001
from textual.widgets import Label
from src.tui.app import GptcgtApp
from src.tui.panels.chat import ChatPanel
from pathlib import Path

@pytest.mark.asyncio
async def test_app_update_chat_context_header():
    app = GptcgtApp()
    app.project_path = Path.cwd()
    async with app.run_test() as pilot:  # noqa: F841
        chat = app.query_one("#right-panel", ChatPanel)
        header = chat.query_one("#chat-input-header", Label)
        assert header is not None
  # noqa: W293
        # Simulate active file
        app._active_file = str(Path("test_file.py"))
        app._active_line = 42
        app._update_chat_context_header()
  # noqa: W293
        # Test header content
        content = str(header.render())
        assert "test_file.py" in content
        assert "42" in content
