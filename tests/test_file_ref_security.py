"""Tests for @file path security — ensures workspace boundary enforcement."""


import pytest

from src.core.workspace import Workspace, WorkspaceEscapeError


@pytest.fixture(autouse=True)
def reset_workspace():
    """Reset workspace singleton before each test."""
    Workspace.reset_instance()
    yield
    Workspace.reset_instance()


@pytest.fixture
def workspace(tmp_path):
    """Create a workspace rooted in a temporary directory."""
    ws = Workspace(tmp_path)
    # Create some files to test with
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "secrets.txt").write_text("should be readable")
    return ws


class TestValidatePath:
    def test_valid_relative_path(self, workspace, tmp_path):
        result = workspace.validate_path("src/main.py")
        assert result == tmp_path / "src" / "main.py"

    def test_valid_absolute_path(self, workspace, tmp_path):
        abs_path = tmp_path / "src" / "main.py"
        result = workspace.validate_path(str(abs_path))
        assert result == abs_path

    def test_rejects_parent_traversal(self, workspace):
        with pytest.raises(WorkspaceEscapeError):
            workspace.validate_path("../../etc/passwd")

    def test_rejects_absolute_outside(self, workspace):
        with pytest.raises(WorkspaceEscapeError):
            workspace.validate_path("/etc/passwd")

    def test_rejects_symlink_escape(self, workspace, tmp_path):
        # Create a symlink that points outside the workspace
        link_path = tmp_path / "sneaky_link"
        try:
            link_path.symlink_to("/tmp")
        except OSError:
            pytest.skip("Cannot create symlinks on this system")
        with pytest.raises(WorkspaceEscapeError):
            workspace.validate_path("sneaky_link/../../etc/passwd")

    def test_rejects_dot_dot_in_middle(self, workspace):
        with pytest.raises(WorkspaceEscapeError):
            workspace.validate_path("src/../../../etc/shadow")


class TestSafeRead:
    def test_safe_read_valid(self, workspace, tmp_path):
        content = workspace.safe_read("src/main.py")
        assert content == "print('hello')"

    def test_safe_read_rejects_escape(self, workspace):
        with pytest.raises(WorkspaceEscapeError):
            workspace.safe_read("../../etc/passwd")


class TestSafeExistsNeverRaises:
    def test_safe_exists_returns_false_for_escape(self, workspace):
        # safe_exists catches WorkspaceEscapeError and returns False
        assert workspace.safe_exists("../../etc/passwd") is False

    def test_safe_exists_returns_true_for_valid(self, workspace):
        assert workspace.safe_exists("src/main.py") is True
