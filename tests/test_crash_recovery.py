from pathlib import Path

import pytest

from src.core.crash_recovery import CrashRecoveryManager, PendingDiffProtector, RecoverableState


@pytest.fixture
def recovery_env(tmp_path):
    project_path = tmp_path / "project"
    project_path.mkdir()
    return project_path


def test_recovery_manager_creates_directories(recovery_env):
    mgr = CrashRecoveryManager(recovery_env)
    assert mgr.recovery_dir.exists()
    assert mgr.recovery_dir.is_dir()


def test_acquire_lock_creates_file(recovery_env):
    mgr = CrashRecoveryManager(recovery_env)
    mgr.acquire_lock()
    assert mgr.lock_file.exists()


def test_save_and_get_state(recovery_env):
    mgr = CrashRecoveryManager(recovery_env)
    test_state = RecoverableState(active_task="task_123", progress=50)
    mgr.save_state(test_state)

    assert mgr.state_file.exists()
    assert mgr.lock_file.exists()  # Auto-creates lock

    recovered = mgr.get_recovered_state()
    assert recovered is not None
    assert recovered.active_task == "task_123"
    assert recovered.progress == 50
    assert recovered._timestamp != ""


def test_check_for_crash_with_stale_lock_but_no_state(recovery_env):
    mgr = CrashRecoveryManager(recovery_env)
    mgr.lock_file.touch()  # Stale lock

    # Should clean up and return False
    assert not mgr.check_for_crash()
    assert not mgr.lock_file.exists()


def test_check_for_crash_with_valid_state(recovery_env):
    mgr = CrashRecoveryManager(recovery_env)
    test_state = RecoverableState(active_task="task_123")
    mgr.save_state(test_state)
    mgr.lock_file.touch()

    assert mgr.check_for_crash() is True


def test_diff_protector_lifecycle(recovery_env):
    prot = PendingDiffProtector(recovery_env)

    test_diff = "--- a.py\n+++ a.py\n+new line"
    test_file = Path("src/core/a.py")

    prot.backup_diff(test_file, test_diff)

    diffs = prot.get_pending_diffs()
    assert len(diffs) == 1
    # Check that a version of the filename is used as a key
    key = list(diffs.keys())[0]
    assert "a.py" in key
    assert diffs[key] == test_diff

    prot.clear_diff(test_file)
    diffs = prot.get_pending_diffs()
    assert len(diffs) == 0
