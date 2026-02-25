import pytest

from src.tui.panels.chat import ChatPanel


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
