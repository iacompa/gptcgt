"""Tests for Onboarding Wizard."""

from src.core.config import ConfigManager


def test_first_run_detected_when_no_global_config(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    cfg = ConfigManager()
    assert not cfg.user.setup_completed


def test_onboarding_skipped_when_config_exists(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    # create fake pre-existing config
    cfg_dir = tmp_path / ".gptcgt"
    cfg_dir.mkdir()
    (cfg_dir / "global.toml").write_text("setup_completed = true\n")

    cfg = ConfigManager()
    assert cfg.user.setup_completed


def test_setup_completed_flag_persists(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    cfg = ConfigManager()
    cfg.set_user("setup_completed", True)

    # Reload from disk
    cfg2 = ConfigManager()
    assert cfg2.user.setup_completed
