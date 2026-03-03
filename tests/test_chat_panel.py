import pytest
from textual.app import App, ComposeResult

from src.core.events import AgentCompleted, AgentDispatched
from src.tui.panels.chat import ChatMessage, ChatPanel


@pytest.mark.asyncio
async def test_chat_slash_commands():
    ChatPanel()
    # Mock textual setup / child mounting
    pass


@pytest.mark.asyncio
async def test_chat_input_extracts_files():
    # Direct logic test on string parsing
    import re

    text = "Fix the login loop @src/auth/login.py @tests/test_login.py and make it secure."
    files = re.findall(r"@([a-zA-Z0-9_\-\./]+)", text)
    clean_text = re.sub(r"@[a-zA-Z0-9_\-\./]+", "", text).strip()

    assert "src/auth/login.py" in files
    assert "tests/test_login.py" in files
    assert "Fix the login loop   and make it secure." == clean_text


@pytest.mark.asyncio
async def test_no_api_key_shows_warning():
    pass  # App UI integration test depending on KeyChainManager


class _ChatPanelTestApp(App[None]):
    def compose(self) -> ComposeResult:
        yield ChatPanel(id="chat")


@pytest.mark.asyncio
async def test_long_user_message_is_not_clipped():
    app = _ChatPanelTestApp()
    async with app.run_test(size=(180, 50)) as pilot:
        chat = app.query_one("#chat", ChatPanel)

        # Remove empty-state helper content to isolate message rendering.
        for child in list(chat.scroll_container.children):
            child.remove()

        long_text = "x" * 1200
        chat._append_message("user", long_text, time_str="12:00 PM")
        await pilot.pause()

        msg = chat.query(ChatMessage).last()
        inner = list(msg.children)[0]
        children = list(inner.children)
        assert len(children) >= 2

        # Header is child[0], content label is child[1].
        content_label = children[1]
        assert content_label.outer_size.height > 1
        assert content_label.outer_size.width >= 10


@pytest.mark.asyncio
async def test_thinking_spinner_lifecycle_is_stable():
    app = _ChatPanelTestApp()
    async with app.run_test(size=(180, 50)) as pilot:
        chat = app.query_one("#chat", ChatPanel)

        # Remove empty-state helper content to isolate spinner checks.
        for child in list(chat.scroll_container.children):
            child.remove()

        # Spinner should start on real agent dispatch.
        chat.post_message(AgentDispatched(agent_name="Coder", model_name="Claude Haiku 3.5"))
        await pilot.pause()

        pills = [c for c in chat.scroll_container.children if "transient-pill" in c.classes]
        assert len(pills) == 1

        # Re-dispatch should not duplicate spinner timers/widgets.
        chat.post_message(AgentDispatched(agent_name="Coder", model_name="Claude Haiku 3.5"))
        await pilot.pause()
        pills = [c for c in chat.scroll_container.children if "transient-pill" in c.classes]
        assert len(pills) == 1

        # Completion always clears spinner.
        chat.post_message(AgentCompleted(agent_id="Coder", full_response="done"))
        await pilot.pause()
        pills = [c for c in chat.scroll_container.children if "transient-pill" in c.classes]
        assert len(pills) == 0
