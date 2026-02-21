"""Tests for Workspace security boundary."""

import pytest
import os
from pathlib import Path
from src.core.workspace import Workspace, WorkspaceEscapeError

@pytest.fixture
def test_workspace(tmp_path):
    """Fixture providing a temporary Workspace instance."""
    Workspace.reset_instance()
    ws = Workspace(project_root=tmp_path)
    return ws, tmp_path

def test_valid_path_inside_project(test_workspace):
    ws, root = test_workspace
    test_file = root / "test.txt"
    test_file.write_text("hello")
    assert ws.safe_read(test_file) == "hello"

def test_path_traversal_blocked(test_workspace):
    ws, root = test_workspace
    with pytest.raises(WorkspaceEscapeError):
        ws.validate_path("../../etc/passwd")

def test_absolute_path_outside_blocked(test_workspace):
    ws, root = test_workspace
    with pytest.raises(WorkspaceEscapeError):
        ws.validate_path("/etc/passwd")

def test_symlink_escape_blocked(test_workspace):
    ws, root = test_workspace
    target = root / "link.txt"
    try:
        os.symlink("/etc/passwd", target)
    except OSError:
        pytest.skip("Symlinks not supported on this platform under these permissions")
        
    with pytest.raises(WorkspaceEscapeError):
        ws.safe_read(target)

def test_dot_dot_in_middle_blocked(test_workspace):
    ws, root = test_workspace
    # We create a nested path, and try to escape it
    with pytest.raises(WorkspaceEscapeError):
        ws.validate_path(root / "subdir" / ".." / ".." / "outside")

def test_ignore_node_modules(test_workspace):
    ws, root = test_workspace
    nm = root / "node_modules"
    nm.mkdir()
    (nm / "index.js").touch()
    
    items = list(ws.safe_walk(root))
    assert len(items) == 1
    assert items[0][0] == root
    assert len(items[0][1]) == 0 # internal dirs in valid_dir_paths is empty

def test_ignore_git_directory(test_workspace):
    ws, root = test_workspace
    git_dir = root / ".git"
    git_dir.mkdir()
    
    items = list(ws.safe_walk(root))
    assert len(items) == 1
    assert len(items[0][1]) == 0

def test_gptcgtignore_custom_patterns(test_workspace):
    ws, root = test_workspace
    (root / ".gptcgtignore").write_text("secret.txt\n")
    
    Workspace.reset_instance()
    ws = Workspace(project_root=root)
    
    (root / "secret.txt").touch()
    
    items = list(ws.safe_walk(root))
    assert len(items) == 1
    
    files = [f.name for f in items[0][2]]
    assert "secret.txt" not in files
    assert ".gptcgtignore" in files

def test_safe_write_inside_project(test_workspace):
    ws, root = test_workspace
    ws.safe_write("new_file.txt", "content")
    assert (root / "new_file.txt").exists()
    assert (root / "new_file.txt").read_text() == "content"

def test_safe_write_outside_blocked(test_workspace):
    ws, root = test_workspace
    with pytest.raises(WorkspaceEscapeError):
        ws.safe_write("../outside.txt", "content")

def test_safe_delete_cannot_delete_root(test_workspace):
    ws, root = test_workspace
    with pytest.raises(PermissionError):
        ws.safe_delete(root)

def test_workspace_singleton(test_workspace):
    ws, root = test_workspace
    ws2 = Workspace.get_instance()
    assert ws is ws2
