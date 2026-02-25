"""Project Initialization Flow."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.core.logger import get_logger

logger = get_logger("core.init")


class ProjectInitializer:
    """Handles first-time project setup and workspace validation."""

    def __init__(self, project_path: Path | None = None) -> None:
        """Determine and validate the project root."""
        if project_path is None:
            self.root = Path.cwd()
        else:
            self.root = Path(project_path).resolve()

    def validate_project_path(self, path: Path) -> dict[str, Any]:
        """Validate that the path is safe and usable."""
        result = {"valid": True, "warnings": [], "errors": [], "path": path}

        if not path.exists():
            result["valid"] = False
            result["errors"].append(f"Path does not exist: {path}")
            return result

        if not path.is_dir():
            result["valid"] = False
            result["errors"].append(f"Path is not a directory: {path}")
            return result

        str(path)
        system_dirs = ["/usr", "/etc", "/System", "/bin", "/sbin", "C:\\Windows"]

        for sdir in system_dirs:
            try:
                # Use strict path comparison to prevent bypasses
                # like /usrlocal being blocked
                if path == Path(sdir) or Path(sdir) in path.parents:
                    result["valid"] = False
                    result["errors"].append(f"Cannot use system directory {sdir}")
            except Exception:
                pass

        # Check if home dir (simple check)
        home = Path.home()
        if path == home:
            result["warnings"].append("This is your home directory. Consider using a subfolder.")

        if not os.access(path, os.W_OK):
            result["valid"] = False
            result["errors"].append(f"Directory is not writable: {path}")

        if not result["valid"]:
            logger.warning(f"Project validation failed for {path}: {result['errors']}")

        return result

    def initialize_project(self) -> None:
        """Set up .gptcgt/ directory for a project."""
        logger.info(f"Initializing project at {self.root}")
        gptcgt_dir = self.root / ".gptcgt"
        if not gptcgt_dir.exists():
            gptcgt_dir.mkdir(parents=True, exist_ok=True)
            # Set restrictive permissions where supported
            try:
                os.chmod(gptcgt_dir, 0o700)
            except Exception:
                pass

        # Auto add to .gitignore
        gitignore = self.root / ".gitignore"
        ignore_entry = "\n# gptcgt project data\n.gptcgt/\n"
        if gitignore.exists():
            text = gitignore.read_text(encoding="utf-8")
            if ".gptcgt/" not in text:
                with open(gitignore, "a", encoding="utf-8") as f:
                    f.write(ignore_entry)
        else:
            with open(gitignore, "w", encoding="utf-8") as f:
                f.write(ignore_entry.lstrip())

        sessions_dir = gptcgt_dir / "sessions"
        sessions_dir.mkdir(exist_ok=True)

        # Write config if absent
        config_file = gptcgt_dir / "config.toml"
        if not config_file.exists():
            config_file.write_text('[project]\nname = "auto-detected"\n', encoding="utf-8")

    def is_initialized(self) -> bool:
        """Check if .gptcgt/ already exists in this path."""
        return (self.root / ".gptcgt").exists()

    def handle_permissions_os_specific(self) -> None:
        """Handle OS-specific file access permissions logic."""
        # Placeholer for more complex checks
        pass
