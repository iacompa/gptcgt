"""
File tree panel for gptcgt.

Displays a collapsible tree of workspace files, with a recently modified section at the top.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import MouseDown
from textual.widgets import Label, Tree

from src.core.events import FileRelevanceUpdated, FileSelected, PatchSetProposed
from src.core.logger import get_logger
from src.core.workspace import Workspace

logger = get_logger("tui.file_tree")


class FileTreePanel(Vertical):
    """Left panel displaying project files and recent files."""

    DEFAULT_CSS = """
    FileTreePanel {
        border-right: none;
        width: 100%;
        height: 100%;
        background: $background;
    }
    .tree-header {
        padding: 0 1;
        background: $surface;
        color: $primary;
        text-style: bold;
        border-bottom: solid $secondary;
        width: 100%;
    }
    #recent-files-tree {
        background: $background;
        padding: 0 0;
        height: auto;
        min-height: 3;
        max-height: 10;
        scrollbar-size: 1 1;
    }
    #project-files-tree {
        background: $background;
        padding: 0 0;
        height: 1fr;
        scrollbar-size: 1 1;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.workspace = Workspace.get_instance()
        self.indicators: dict[Path, str] = {}

    def compose(self) -> ComposeResult:
        # Security badge — visible proof the workspace is jailed
        root_name = self.workspace.get_project_root().name
        yield Label(f"🔒 Sandboxed: {root_name}", classes="tree-header", id="sandbox-badge")

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
        # Toast on first load so users know they're safe
        root_name = self.workspace.get_project_root().name
        self.app.notify(f"🔒 Workspace locked to '{root_name}' — AI cannot access other folders", timeout=5)

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
                parent_node.add(self._format_label(filename), data=filename, allow_expand=False)

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
            self.recent_tree.root.add(str(rel_path), data=f, allow_expand=False)

    def _format_label(self, path: Path) -> str:
        """Format the file label with type icon and state indicators."""
        state = self.indicators.get(path, "normal")
        name = path.name
        ext = path.suffix.lower()

        # File type icons
        _icons = {
            ".py": "🐍",
            ".ts": "📘",
            ".tsx": "⚛️",
            ".js": "🐛",
            ".jsx": "⚛️",
            ".json": "⚙️",
            ".md": "📝",
            ".yml": "📜",
            ".yaml": "📜",
            ".toml": "📜",
            ".sh": "📦",
            ".dockerfile": "🐳",
            ".env": "🔐",
            ".css": "🎨",
            ".html": "🌐",
            ".sql": "🗃️",
            ".rs": "🧡",
            ".go": "💧",
            ".proto": "🔗",
            ".lock": "🔒",
        }
        # Special filename handling
        _special = {
            "dockerfile": "🐳",
            "makefile": "⚙️",
            ".gitignore": "🙈",
            "readme.md": "📖",
        }

        icon = _special.get(name.lower()) or _icons.get(ext) or "📄"

        # State indicators override icon prefix
        if state == "in_context":
            return f"🔵 {icon} {name}"
        elif state == "proposed":
            return f"🟠 {icon} {name}"
        elif state == "applied":
            return f"✅ {icon} {name}"
        return f"{icon} {name}"

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
        except Exception as e:
            logger.debug(f"update_indicator failed for {filepath}: {e}")

    def _clear_indicator(self, filepath: Path) -> None:
        """Clear an indicator."""
        if filepath in self.indicators:
            self.indicators[filepath] = "normal"
            self.project_tree.clear()
            self._build_project_tree()

    def on_tree_node_selected(self, message: Tree.NodeSelected) -> None:
        """Handle leaf node selections."""
        if message.node.data:
            path: Path = message.node.data
            if path.is_file():
                logger.info(f"File selected from tree: {path}")
                self.post_message(FileSelected(path))

    def on_mouse_down(self, event: MouseDown) -> None:
        """Handle right click for file tree context menus."""
        if event.button == 3:  # Right click
            # Detect which file node was right-clicked
            clicked_path: Path | None = None
            try:
                node = self.project_tree.get_node_at_line(event.y)
                if node and node.data and isinstance(node.data, Path) and node.data.is_file():
                    clicked_path = node.data
            except Exception:
                pass

            logger.debug(f"Right click in file tree, path={clicked_path}")
            from src.tui.widgets.context_menu import ContextMenuSpawner
            from src.tui.widgets.menu import MenuItem

            if clicked_path:
                file_name = clicked_path.name
                items = [
                    MenuItem(f"🐍 Explain '{file_name}'", action=f"ai_explain_file|{clicked_path}"),
                    MenuItem(f"🐛 Find Bugs in '{file_name}'", action=f"ai_bugs_file|{clicked_path}"),
                    MenuItem(f"🧪 Write Tests for '{file_name}'", action=f"ai_tests_file|{clicked_path}"),
                    MenuItem("📎 Add to Chat Context", action=f"tree_add_context|{clicked_path}"),
                    MenuItem(is_separator=True),
                    MenuItem("Copy Relative Path", action="tree_copy_path"),
                    MenuItem("Reveal in Finder", action="tree_reveal"),
                ]
            else:
                items = [
                    MenuItem("New File...", action="tree_new_file"),
                    MenuItem("New Folder...", action="tree_new_folder"),
                    MenuItem(is_separator=True),
                    MenuItem("💡 Explain Project", action="ai_explain_project"),
                    MenuItem("🐛 Find All Bugs", action="ai_bugs_project"),
                    MenuItem(is_separator=True),
                    MenuItem("Copy Relative Path", action="tree_copy_path"),
                    MenuItem("Reveal in Finder", action="tree_reveal"),
                ]
            ContextMenuSpawner.spawn(self.app, event, items)
            event.stop()

    def _handle_ai_tree_action(self, action: str) -> None:
        """Handle AI context-menu actions from file tree."""
        from src.core.events import TaskReceived

        if "|" in action:
            cmd, path_str = action.split("|", 1)
            file_path = Path(path_str)
            prompts = {
                "ai_explain_file": f"Explain what '{file_path.name}' does and how it fits the project.",
                "ai_bugs_file": f"Scan '{file_path.name}' for bugs, security issues, and code smells.",
                "ai_tests_file": f"Write comprehensive unit tests for '{file_path.name}'.",
                "tree_add_context": None,  # handled separately
            }
            if cmd == "tree_add_context":
                from src.core.events import ContextModified

                self.app.post_message(ContextModified(action="add", file_path=str(file_path)))
                from src.tui.widgets.toast import notify

                notify(self.app, "Context", f"Added {file_path.name} to chat context.", "info")
            elif cmd in prompts and prompts[cmd]:
                self.app.post_message(TaskReceived(task_str=prompts[cmd], attached_files=[file_path]))
        elif action == "ai_explain_project":
            self.app.post_message(
                TaskReceived(task_str="Explain what this project does and its overall architecture.", attached_files=[])
            )  # noqa: E501
        elif action == "ai_bugs_project":
            self.app.post_message(
                TaskReceived(
                    task_str="Scan the codebase for bugs, security issues, and code smells.", attached_files=[]
                )
            )  # noqa: E501

    @on(FileRelevanceUpdated)
    def highlight_relevant_files(self, event: FileRelevanceUpdated) -> None:
        for f in event.files:
            self.update_indicator(Path(f), "in_context")

    @on(PatchSetProposed)
    def highlight_patched_files(self, event: PatchSetProposed) -> None:
        for p in event.patch_set.patches:
            self.update_indicator(Path(p.file_path), "proposed")
