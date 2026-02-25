"""Modal overlay for Project Setup on first run."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

if TYPE_CHECKING:
    from src.core.init import ProjectInitializer
    from src.core.workspace import Workspace


class ProjectSetupScreen(ModalScreen[bool]):
    """Shown when gptcgt launches in a folder without .gptcgt/"""

    DEFAULT_CSS = """
    ProjectSetupScreen {
        align: center middle;
        background: $surface 80%;
    }

    #setup-dialog {
        width: 70;
        height: auto;
        background: $panel;
        border: solid $primary;
        padding: 2 4;
    }
    """

    def __init__(
        self, initializer: "ProjectInitializer", workspace: "Workspace", *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.initializer = initializer
        self.workspace = workspace

    def compose(self) -> ComposeResult:
        with Vertical(id="setup-dialog"):
            yield Label("Project Setup", classes="text-style-bold text-center")
            yield Label(f"\ngptcgt will work in this folder:\n\n📁 {self.initializer.root}\n")

            yield Label("gptcgt will:")
            yield Label("✅ Read files in this folder and all subfolders")
            yield Label("✅ Create a .gptcgt/ folder for project data")
            yield Label("✅ Write AI-proposed changes to files (with your approval)")

            yield Label("\ngptcgt will NEVER:")
            yield Label("🔒 Access files outside this folder")
            yield Label("🔒 Access your home directory, system files, or other projects")
            yield Label("🔒 Send your code to our servers (BYOK calls go direct)")
            yield Label("🔒 Modify files without your explicit approval\n")

            with Horizontal():
                yield Button("✓ Looks good, start", id="btn-start", variant="primary")
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-start":
            # Init!
            self.initializer.initialize_project()

            # Generate phase.md
            from src.core.phase_tracker import PhaseTracker

            tracker = PhaseTracker(self.workspace)
            tracker.ensure_loaded()

            self.dismiss(True)
        elif event.button.id == "btn-cancel":
            self.app.exit()


class PathErrorScreen(ModalScreen[None]):
    """Shown when the selected workspace path is invalid (e.g., system root `/`)."""

    DEFAULT_CSS = """
    PathErrorScreen {
        align: center middle;
        background: $surface 80%;
    }

    #error-dialog {
        width: 60;
        height: auto;
        background: $error 20%;
        border: solid $error;
        padding: 2 4;
    }
    """

    def __init__(self, errors: list[str], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.errors = errors

    def compose(self) -> ComposeResult:
        with Vertical(id="error-dialog"):
            yield Label("⚠️ Invalid Workspace Path", classes="text-style-bold text-center")
            yield Label("\ngptcgt cannot run in this directory for security reasons:\n")
            for err in self.errors:
                yield Label(f"• {err}")
            yield Label("\nPlease change directories or provide a valid path.\n")
            yield Button("Exit", id="btn-exit", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.app.exit()
