from __future__ import annotations

import pytest

from src.core.config import ConfigManager
from src.core.workspace import Workspace
from src.tui.app import GptcgtApp


@pytest.mark.asyncio
async def test_app(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    ConfigManager.reset_instance()
    Workspace.reset_instance()

    app = GptcgtApp(project_path=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.apply_layout("default")
        await pilot.pause()

    ConfigManager.reset_instance()
    Workspace.reset_instance()
