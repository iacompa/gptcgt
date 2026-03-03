
import pytest

from src.core.diff_engine import DiffExtractor
from src.core.workspace import Workspace


@pytest.fixture
def mock_workspace(tmp_path, monkeypatch):
    """Sets up a safe temporary workspace for file reads."""
    class MockWorkspace:
        def __init__(self, root):
            self.root = root

        @classmethod
        def get_instance(cls):
            return cls(tmp_path)

        def get_project_root(self):
            return self.root

        def safe_exists(self, path):
            return (self.root / path).exists()

        def safe_read(self, path):
            return (self.root / path).read_text()

        def safe_write(self, path, content):
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text(content)

    monkeypatch.setattr(Workspace, "get_instance", MockWorkspace.get_instance)
    return MockWorkspace(tmp_path)


def test_syntax_valid_on_good_patch(mock_workspace):
    """Tests that a valid python diff passes AST validation."""
    mock_workspace.safe_write("test_good.py", "def foo():\n    pass\n")

    diff_text = """
```python
# test_good.py
def foo():
    print("hello world")
```
"""
    extractor = DiffExtractor()
    patch_set = extractor.extract(diff_text)

    assert len(patch_set.patches) == 1
    fp = patch_set.patches[0]
    assert fp.file_path == "test_good.py"
    assert getattr(fp, "syntax_valid", False) is True
    assert getattr(fp, "syntax_error", None) is None


def test_syntax_invalid_on_bad_patch(mock_workspace):
    """Tests that an invalid python diff fails AST validation and captures the error."""
    mock_workspace.safe_write("test_bad.py", "def foo():\n    pass\n")

    # Missing closing quote and parenthesis
    diff_text = """
```python
# test_bad.py
def foo():
    print("hello world
```
"""
    extractor = DiffExtractor()
    patch_set = extractor.extract(diff_text)

    assert len(patch_set.patches) == 1
    fp = patch_set.patches[0]
    assert fp.file_path == "test_bad.py"
    assert getattr(fp, "syntax_valid", True) is False
    assert getattr(fp, "syntax_error", None) is not None
    assert "Syntax" in fp.syntax_error or "unterminated string literal" in fp.syntax_error

def test_syntax_validation_skipped_for_non_python(mock_workspace):
    """Tests that non-python files are always marked as syntax_valid."""
    mock_workspace.safe_write("test_doc.md", "# Hello\n")

    diff_text = """
```markdown
# test_doc.md
# Hello {
```
"""
    extractor = DiffExtractor()
    patch_set = extractor.extract(diff_text)

    assert len(patch_set.patches) == 1
    fp = patch_set.patches[0]
    assert fp.file_path == "test_doc.md"
    assert getattr(fp, "syntax_valid", False) is True
