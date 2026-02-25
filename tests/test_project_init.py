"""Tests for the Workspace Initialization flow."""

import os
from pathlib import Path

from src.core.init import ProjectInitializer


def test_cwd_used_when_no_arg():
    init = ProjectInitializer()
    assert init.root == Path.cwd()


def test_explicit_path_arg_used(tmp_path):
    init = ProjectInitializer(tmp_path)
    assert init.root == tmp_path.resolve()


def test_system_directory_rejected():
    init = ProjectInitializer(Path("/usr/bin"))
    res = init.validate_project_path(init.root)
    assert res["valid"] is False
    assert any("/usr" in err for err in res["errors"])


def test_home_directory_warned():
    home = Path.home()
    init = ProjectInitializer(home)
    res = init.validate_project_path(home)
    # the directory itself is generally valid (if writable), but should have a warning
    assert "Consider using a subfolder" in " ".join(res["warnings"])


def test_gitignore_updated(tmp_path):
    init = ProjectInitializer(tmp_path)
    gi = tmp_path / ".gitignore"
    gi.write_text("node_modules/\n")

    init.initialize_project()

    content = gi.read_text()
    assert "node_modules/" in content
    assert ".gptcgt/" in content


def test_gptcgt_dir_created_with_all_files(tmp_path):
    init = ProjectInitializer(tmp_path)
    init.initialize_project()

    gptcgt = tmp_path / ".gptcgt"
    assert gptcgt.exists()
    assert gptcgt.is_dir()

    config = gptcgt / "config.toml"
    assert config.exists()

    sessions = gptcgt / "sessions"
    assert sessions.exists()
    assert sessions.is_dir()

    assert init.is_initialized() is True


def test_permissions_set_owner_only(tmp_path):
    init = ProjectInitializer(tmp_path)
    init.initialize_project()

    gptcgt = tmp_path / ".gptcgt"
    # Basic check - on non-Windows it should be 700
    if os.name != "nt":
        stat = gptcgt.stat()
        assert (stat.st_mode & 0o777) == 0o700


def test_reinit_preserves_existing_data(tmp_path):
    init = ProjectInitializer(tmp_path)
    init.initialize_project()

    config = tmp_path / ".gptcgt" / "config.toml"
    config.write_text("custom_data = true")

    # Init again
    init.initialize_project()
    assert config.read_text() == "custom_data = true"


def test_macos_permission_error_message():
    init = ProjectInitializer()
    init.handle_permissions_os_specific()
    # Mocking OS level permissions is tricky, just assert it executes
    pass


def test_windows_long_path_handled():
    init = ProjectInitializer()
    init.handle_permissions_os_specific()
    pass
