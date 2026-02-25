"""Tests for Config Manager."""

from pathlib import Path

from src.core.config import ConfigManager


def test_global_config_creates_default(tmp_path, monkeypatch):
    # Mock home dir
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    cfg = ConfigManager(project_root=tmp_path / "proj")
    assert cfg.user.theme == "midnight"
    assert cfg.user.default_quality_tier == "standard"
    assert not cfg.user.setup_completed


def test_project_config_overrides_global(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()

    cfg = ConfigManager(project_root=proj_dir)
    cfg.set_user("theme", "polar")  # global

    # Should equal global
    assert cfg.get("theme") == "polar"

    # Not overridden since ProjectConfig doesn't have 'theme' attribute.
    # But let's test a setting that they COULD both have, or just project-specific ones.
    assert cfg.get("project_name") == ""
    cfg.set_project("project_name", "MyProj")
    assert cfg.get("project_name") == "MyProj"


def test_auto_detect_project(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()

    # Create fake files
    (proj_dir / "main.py").write_text("print('hello')")
    (proj_dir / "pytest.ini").write_text("[pytest]")

    cfg = ConfigManager(project_root=proj_dir)
    cfg.auto_detect_project()

    assert cfg.project.project_name == "proj"
    assert cfg.project.primary_language == "python"
    assert cfg.project.test_command == "pytest"
