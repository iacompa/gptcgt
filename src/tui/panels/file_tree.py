"""File tree panel for gptcgt.

Displays a collapsible tree of workspace files, with a recently modified section at the top.
"""

from pathlib import Path
from typing import Any
from textual.app import ComposeResult
from textual.widgets import Tree, Label
from textual.containers import Vertical

from src.core.workspace import Workspace
from src.core.events import FileSelected

class FileTreePanel(Vertical):
    """Left panel displaying project files and recent files."""
    
    DEFAULT_CSS = """
    FileTreePanel {
        border-right: solid #30363D;
        width: 100%;
        height: 100%;
    }
    .tree-header {
        padding: 1;
        background: #1C2333;
        color: #E6EDF3;
        text-style: bold;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.workspace = Workspace.get_instance()
        self.indicators: dict[Path, str] = {}

    def compose(self) -> ComposeResult:
        yield Label("Recently Modified", classes="tree-header")
        self.recent_tree = Tree("Recent Files", id="recent-files-tree")
        self.recent_tree.root.expand()
        self.recent_tree.show_root = False
        yield self.recent_tree
        
        yield Label("Project Files", classes="tree-header")
        self.project_tree = Tree("Project", id="project-files-tree")
        self.project_tree.root.expand()
        self.project_tree.show_root = False
        yield self.project_tree

    def on_mount(self) -> None:
        """Build the trees on mount."""
        self._build_project_tree()
        self._build_recent_tree()

    def _build_project_tree(self) -> None:
        """Populate the project tree using Workspace safely."""
        root_path = self.workspace.get_project_root()
        
        # A dictionary to map Path to Tree Node
        nodes = {root_path: self.project_tree.root}
        
        # Use safe_walk from workspace
        for dirpath, dirnames, filenames in self.workspace.safe_walk(root_path):
            parent_node = nodes.get(dirpath)
            if not parent_node:
                continue
                
            # Add directories
            for dirname in sorted(dirnames, key=lambda p: p.name.lower()):
                node = parent_node.add(dirname.name, data=dirname, expand=False)
                nodes[dirname] = node
                
            # Add files
            for filename in sorted(filenames, key=lambda p: p.name.lower()):
                parent_node.add(self._format_label(filename), data=filename, leaf=True)

    def _build_recent_tree(self) -> None:
        """Populate the recent files tree."""
        root_path = self.workspace.get_project_root()
        all_files = []
        
        # Collect all files to sort by mtime
        for dirpath, _, filenames in self.workspace.safe_walk(root_path):
            for f in filenames:
                try:
                    stat = f.stat()
                    all_files.append((f, stat.st_mtime))
                except OSError:
                    pass
                    
        # Sort desc by mtime, take top 5
        all_files.sort(key=lambda x: x[1], reverse=True)
        recent = all_files[:5]
        
        for f, _ in recent:
            rel_path = f.relative_to(root_path)
            self.recent_tree.root.add(str(rel_path), data=f, leaf=True)

    def _format_label(self, path: Path) -> str:
        """Format the file label with indicators if present."""
        state = self.indicators.get(path, "normal")
        name = path.name
        
        if state == "in_context":
            return f"🔵 {name}"
        elif state == "proposed":
            return f"🟠 {name}"
        elif state == "applied":
            return f"✅ {name}"
        return name

    def update_indicator(self, filepath: Path, state: str) -> None:
        """Update the visual indicator for a file."""
        try:
            abs_path = self.workspace.validate_path(filepath)
            self.indicators[abs_path] = state
            
            self.project_tree.clear()
            self._build_project_tree()
            
            if state == "applied":
                # Auto-clear after 3 seconds
                self.set_timer(3.0, lambda: self._clear_indicator(abs_path))
        except Exception:
            pass

    def _clear_indicator(self, filepath: Path) -> None:
        """Clear an indicator."""
        if filepath in self.indicators:
            self.indicators[filepath] = "normal"
            self.project_tree.clear()
            self._build_project_tree()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        # Only emit on leaf selection (files)
        if event.node.allow_expand is False and event.node.data:
            self.post_message(FileSelected(event.node.data))
