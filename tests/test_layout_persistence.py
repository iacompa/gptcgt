import pytest

from src.core.config import ConfigManager, UserConfig  # noqa: F401
from src.tui.app import GptcgtApp


@pytest.fixture
def mock_config(tmp_path):
    ConfigManager.reset_instance()
    mgr = ConfigManager(project_root=tmp_path)
    mgr.GLOBAL_PATH = tmp_path / "global_config.toml"
    mgr.user.panel_positions = {"files": "left", "code": "center", "chat": "right"}
    mgr.user.panel_sizes = {"files": 0.2, "code": 0.6, "chat": 0.2}
    mgr.user.visible_panels = {"files": True, "code": True, "chat": True}
    mgr._save_global()
    yield mgr
    ConfigManager.reset_instance()


@pytest.mark.asyncio
async def test_layout_editor_move_panel(mock_config, tmp_path):
    app = GptcgtApp()
    app.project_path = tmp_path
    app.config = mock_config

    async with app.run_test() as pilot:
        # Move files to right
        app.action_move_panel("files", "right")
        await pilot.pause(0.1)

        # Check config update
        assert app.config.user.panel_positions["files"] == "right"
        assert app.config.user.panel_positions["chat"] == "left"  # Should have swapped

        # Move code to top
        app.action_move_panel("code", "top")
        await pilot.pause(0.1)

        assert app.config.user.panel_positions["code"] == "top"

        # Verify DOM updates (docking)
        code_panel = app.query_one("#code-viewer")
        assert code_panel.styles.dock == "top"


@pytest.mark.asyncio
async def test_layout_preset_application(mock_config, tmp_path):
    app = GptcgtApp()
    app.project_path = tmp_path
    app.config = mock_config

    async with app.run_test() as pilot:
        # Ensure all panels are visible so normalization yields 1:1 with raw sizes
        app.config.user.visible_panels = {"files": True, "code": True, "chat": True}
        app.apply_size("wide_chat")
        await pilot.pause(0.1)

        assert app.config.user.panel_sizes["chat"] == 0.4

        left = app.query_one("#left-panel-container")
        right = app.query_one("#right-panel")

        # Validate that the wide_chat preset makes the right (chat) panel wider
        # than the left (files) panel. Exact fraction values depend on Textual
        # normalization internals, so we check the relative ordering instead.
        left_w = left.styles.width
        right_w = right.styles.width
        assert left_w is not None and right_w is not None, "Panel widths not set"
        assert right_w.value > left_w.value, (
            f"Chat panel ({right_w}) should be wider than file panel ({left_w}) "
            f"after wide_chat preset"
        )
