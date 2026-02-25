"""Tests for PhaseTracker."""

import pytest

from src.core.phase_tracker import PhaseTracker
from src.core.workspace import Workspace


@pytest.fixture
def workspace(tmp_path):
    # Reset singleton state for tests
    Workspace._instance = None
    Workspace._project_root = None
    return Workspace(tmp_path)


@pytest.fixture
def mock_project(tmp_path):
    # Setup some files
    (tmp_path / "src").mkdir()
    f1 = tmp_path / "src" / "app.py"
    f1.write_text("import sys\nprint('hello')\n")

    (tmp_path / "docs").mkdir()
    f2 = tmp_path / "docs" / "readme.md"
    f2.write_text("# Docs\nAwesome.")

    # Create ignore
    (tmp_path / ".gptcgt").mkdir()
    (tmp_path / ".gptcgt" / "phase.md").write_text("# Old Phase")
    return tmp_path


def test_generate_initial_scans_all_files(workspace, mock_project):
    tracker = PhaseTracker(workspace)
    content = tracker.generate_initial()
    workspace.safe_write(tracker.phase_file_path, content)
    tracker.parse_markdown(content)

    assert "src/app.py" in content
    assert "docs/readme.md" in content
    # Should ignore .gptcgt files
    assert "phase.md" not in tracker._file_map


def test_file_map_includes_line_counts(workspace, mock_project):
    tracker = PhaseTracker(workspace)
    content = tracker.generate_initial()
    workspace.safe_write(tracker.phase_file_path, content)
    tracker.parse_markdown(content)

    entry = tracker._file_map.get("src/app.py")
    assert entry is not None
    assert entry.lines == 2


def test_update_after_task_changes_status(workspace, mock_project):
    tracker = PhaseTracker(workspace)
    content = tracker.generate_initial()
    workspace.safe_write(tracker.phase_file_path, content)
    tracker.parse_markdown(content)

    # Mock a task changing docs
    new_doc = mock_project / "docs" / "new.md"
    new_doc.write_text("Hello\nWorld\n")

    tracker.update_after_task(
        task_title="Add new docs", files_changed=["docs/new.md"], _task_outcome="completed"
    )

    entry = tracker._file_map.get("docs/new.md")
    assert entry is not None
    assert entry.lines == 2
    assert "docs/new.md" in tracker._changelog[0]["files"]


def test_get_context_summary_is_compact(workspace, mock_project):
    tracker = PhaseTracker(workspace)
    content = tracker.generate_initial()
    workspace.safe_write(tracker.phase_file_path, content)
    tracker.parse_markdown(content)

    summary = tracker.get_context_summary()
    assert "Project:" in summary
    assert "Phase 1 (in progress)" in summary
    assert "Key files" in summary
    # Should be relatively short compared to rendering the full markdown
    assert len(summary) < 500


def test_get_file_map_for_task_finds_relevant(workspace, mock_project):
    tracker = PhaseTracker(workspace)
    content = tracker.generate_initial()
    workspace.safe_write(tracker.phase_file_path, content)
    tracker.parse_markdown(content)

    tracker.add_file("auth.py", purpose="Authentication logic")
    tracker.add_file("tests/auth.py", purpose="Auth tests")

    res = tracker.get_file_map_for_task(["auth"])
    paths = [e.path for e in res]
    assert "auth.py" in paths
    assert "tests/auth.py" in paths


def test_dependency_graph_follows_imports(workspace, mock_project):
    # Future feature test (stubbed)
    pass


def test_changelog_records_updates(workspace, mock_project):
    tracker = PhaseTracker(workspace)
    content = tracker.generate_initial()
    workspace.safe_write(tracker.phase_file_path, content)
    tracker.parse_markdown(content)
    tracker.update_after_task("Bugfix", ["src/app.py"], "completed")
    tracker.update_after_task("Feature", ["src/app.py"], "completed")

    assert len(tracker._changelog) == 2
    assert tracker._changelog[0]["change"] == "Feature"
    assert tracker._changelog[1]["change"] == "Bugfix"


def test_parse_and_render_roundtrip(workspace, mock_project):
    tracker = PhaseTracker(workspace)
    content = tracker.generate_initial()

    # Save, clear, and parse
    workspace.safe_write(tracker.phase_file_path, content)
    tracker._file_map.clear()

    tracker.parse_markdown(content)

    # Asserts
    assert len(tracker._file_map) > 0
    assert len(tracker._phases) > 0
    assert tracker._phases[0].number == 1
