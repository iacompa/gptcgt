"""Workspace security boundary for gptcgt."""

from __future__ import annotations

import fnmatch
import os
import shutil
from pathlib import Path
from typing import Iterator

from src.core.logger import get_logger

logger = get_logger("core.workspace")


class WorkspaceEscapeError(PermissionError):
    """Raised when an operation attempts to access files outside the project boundary."""

    pass


class Workspace:
    """Security gatekeeper for all file operations."""

    _instance: "Workspace | None" = None

    DEFAULT_IGNORES: set[str] = {
        "node_modules",
        ".git",
        "__pycache__",
        "venv",
        ".venv",
        "dist",
        "build",
        ".eggs",
        "*.egg-info",
        ".tox",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
    }

    def __init__(self, project_root: str | Path | None = None) -> None:
        """Initialize the workspace with a locked project root."""
        if Workspace._instance is not None:
            raise RuntimeError("Workspace is a singleton. Use Workspace.get_instance()")

        root = project_root if project_root is not None else os.getcwd()
        self.project_root = Path(root).resolve()

        self._custom_ignores: list[str] = []
        self._load_gptcgtignore()

        Workspace._instance = self

    @classmethod
    def get_instance(cls) -> "Workspace":
        """
        Get the singleton instance, prioritizing initialization if needed.

        If not initialized, initializes with os.getcwd().
        """
        if cls._instance is None:
            cls(os.getcwd())
        return cls._instance  # type: ignore

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (primarily for testing)."""
        cls._instance = None

    def _load_gptcgtignore(self) -> None:
        """Load custom ignore patterns from .gptcgtignore if it exists."""
        ignore_path = self.project_root / ".gptcgtignore"
        if ignore_path.exists() and ignore_path.is_file():
            try:
                content = ignore_path.read_text(encoding="utf-8")
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self._custom_ignores.append(line)
            except Exception:
                pass  # Safely ignore read errors for the ignore file itself

    def get_project_root(self) -> Path:
        """Return the locked absolute project root."""
        return self.project_root

    def validate_path(self, target: str | Path) -> Path:
        """
        Validate that a path is safely within the project boundary.

        Args:
            target: The path to validate.

        Returns:
            The resolved absolute Path if safe.

        Raises:
            WorkspaceEscapeError: If the path escapes the project root.

        """
        target_path = Path(target)
        if not target_path.is_absolute():
            # Treat relative paths as relative to project_root
            target_path = self.project_root / target_path

        try:
            # Resolving removes all inner ../ and normalizes symlinks
            resolved_path = target_path.resolve()
        except Exception:
            resolved_path = target_path.absolute()

        try:
            resolved_path.relative_to(self.project_root)
        except ValueError:
            logger.critical(
                f"Security boundary violation attempt: {target} escapes {self.project_root}"
            )
            raise WorkspaceEscapeError(
                f"Access denied: {target} is outside the project boundary {self.project_root}"
            )

        return resolved_path

    def is_ignored(self, path: Path) -> bool:
        """
        Check if a path should be ignored based on DEFAULT_IGNORES and .gptcgtignore.

        Args:
            path: The path to check (absolute or relative to project root).

        Returns:
            True if ignored, False otherwise.

        """
        name = path.name

        # Check defaults (exact match for directories or standard wildcard for eggs)
        for pattern in self.DEFAULT_IGNORES:
            if fnmatch.fnmatch(name, pattern):
                return True

        # Check custom ignores against relative path or name
        try:
            rel_path = path.relative_to(self.project_root)
            rel_str = str(rel_path)
            for pattern in self._custom_ignores:
                if fnmatch.fnmatch(rel_str, pattern) or fnmatch.fnmatch(name, pattern):
                    return True
        except ValueError:
            pass

        return False

    def safe_read(self, filepath: str | Path) -> str:
        """Read a file safely."""
        safe_p = self.validate_path(filepath)
        logger.debug(f"Reading file: {safe_p}")
        return safe_p.read_text(encoding="utf-8")

    def safe_write(self, filepath: str | Path, content: str) -> None:
        """Write to a file safely."""
        safe_p = self.validate_path(filepath)
        logger.info(f"Writing to file: {safe_p}")
        safe_p.parent.mkdir(parents=True, exist_ok=True)
        safe_p.write_text(content, encoding="utf-8")

    def safe_listdir(self, dirpath: str | Path) -> list[Path]:
        """List directory contents safely."""
        safe_p = self.validate_path(dirpath)
        if not safe_p.is_dir():
            return []

        items = []
        for child in safe_p.iterdir():
            if not self.is_ignored(child):
                items.append(child)
        return items

    def safe_exists(self, filepath: str | Path) -> bool:
        """Check if a path exists safely."""
        try:
            safe_p = self.validate_path(filepath)
            return safe_p.exists()
        except WorkspaceEscapeError:
            return False

    def safe_walk(self, dirpath: str | Path) -> Iterator[tuple[Path, list[Path], list[Path]]]:
        """
        Walk a directory structure safely.

        Yields:
            (dirpath, dirnames, filenames) where all paths are validated absolute Paths.

        """
        safe_p = self.validate_path(dirpath)

        for root, dirs, files in os.walk(safe_p, topdown=True):
            root_path = Path(root)

            # Filter dirs in-place to prevent walking into ignored ones
            valid_dirs = []
            for d in dirs:
                d_path = root_path / d
                if not self.is_ignored(d_path):
                    valid_dirs.append(d)
            dirs[:] = valid_dirs

            valid_file_paths = []
            for f in files:
                f_path = root_path / f
                if not self.is_ignored(f_path):
                    valid_file_paths.append(f_path)

            valid_dir_paths = [root_path / d for d in dirs]

            yield root_path, valid_dir_paths, valid_file_paths

    def safe_delete(self, filepath: str | Path) -> None:
        """Delete a file or directory safely."""
        safe_p = self.validate_path(filepath)

        if safe_p == self.project_root:
            logger.error("Attempted to delete the project root.")
            raise PermissionError("Cannot delete the project root.")

        if not safe_p.exists():
            return

        logger.warning(f"Deleting path: {safe_p}")
        if safe_p.is_dir():
            shutil.rmtree(safe_p)
        else:
            safe_p.unlink()
