import pytest

from src.core.config import UserConfig  # noqa: F401
from src.tui.app import GptcgtApp


@pytest.fixture
def mock_config(tmp_path):
    from src.core.config import ConfigManager
    config_file = tmp_path / "global_config.toml"
  # noqa: W293
    mgr = ConfigManager()
    mgr.global_config_path = str(config_file)
    mgr.user.panel_positions={"files": "left", "code": "center", "chat": "right"}
    mgr.user.panel_sizes={"files": 0.2, "code": 0.6, "chat": 0.2}
    mgr.user.visible_panels={"files": True, "code": True, "chat": True}
    mgr._save_global()
    return mgr

@pytest.mark.asyncio
async def test_layout_editor_move_panel(mock_config, tmp_path):
    app = GptcgtApp()
    app.project_path = tmp_path
    app.config = mock_config # override
  # noqa: W293
    async with app.run_test() as pilot:
        # Move files to right
        app.action_move_panel("files", "right")
        await pilot.pause(0.1) # allow async task to run
  # noqa: W293
        # Check config update
        assert app.config.user.panel_positions["files"] == "right"
        assert app.config.user.panel_positions["chat"] == "left" # Should have swapped
  # noqa: W293
        # Move code to top
        app.action_move_panel("code", "top")
        await pilot.pause(0.1)
  # noqa: W293
        assert app.config.user.panel_positions["code"] == "top"
  # noqa: W293
        # Verify DOM updates (docking)
        code_panel = app.query_one("#code-viewer")
        assert code_panel.styles.dock == "top"

@pytest.mark.asyncio
async def test_layout_preset_application(mock_config, tmp_path):
    app = GptcgtApp()
    app.project_path = tmp_path
    app.config = mock_config
  # noqa: W293
    async with app.run_test() as pilot:
        # Ensure all panels are visible so normalization yields 1:1 with raw sizes
        app.config.user.visible_panels = {"files": True, "code": True, "chat": True}
        app.apply_size("wide_chat")
        await pilot.pause(0.1)
  # noqa: W293
        assert app.config.user.panel_sizes["chat"] == 0.4
  # noqa: W293
        left = app.query_one("#left-panel-container")
        center = app.query_one("#code-viewer")  # noqa: F841
        right = app.query_one("#right-panel")
  # noqa: W293
        # wide_chat = files:0.15, code:0.45, chat:0.4 → sum=1.0 → normalized as fr units
        assert str(left.styles.width) in ("15.0%", "15w", "15.0w", "0.15fr")
        assert str(right.styles.width) in ("40.0%", "40w", "40.0w", "0.4fr")
