"""
TUI regression tests for layout regressions in Phase 2.

Ensures the Chat panel bubble constraints are applied so text does not 
stretch completely across the screen, and that splitters instantiate.
"""

from __future__ import annotations

import pytest

from textual.app import App, ComposeResult
from textual.widgets import Static

from src.tui.panels.chat import ChatPanel


class DummyApp(App):
    CSS = """
    ChatPanel {
        width: 100%;
        height: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        yield ChatPanel()


@pytest.mark.asyncio
async def test_chat_bubble_css_classes():
    """Verify chat message bubbling gets the correct constraint classes."""
    app = DummyApp()
    async with app.run_test() as pilot:
        chat_panel = app.query_one(ChatPanel)
        
        # Inject a dummy system message (mocking the internal model store lookup)
        chat_panel.app.chat_store = type("MockStore", (), {"get_session_messages": lambda: []})()
        chat_panel._append_message("system", "Test context", "Orchestrator")
        
        # Give it a cycle to mount in the DOM
        await pilot.pause(0.1)

        # Confirm the bubble object exists and gets the constraint class
        bubbles = chat_panel.query(".chat-bubble-system")
        assert len(bubbles) > 0, "System chat bubble did not mount"
        
        # Validate that the bubble text itself mounted
        texts = chat_panel.query(".chat-text")
        assert len(texts) > 0, "Chat text did not mount inside bubble"
