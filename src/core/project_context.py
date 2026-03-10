"""
Auto-generates .gptcgt/project.md by scanning the project.
Detects language, framework, test runner, linter, and project structure.
Runs on first open (no .gptcgt/ exists) and on /reindex command.
"""

from __future__ import annotations

from pathlib import Path

from src.core.logger import get_logger
from src.core.workspace import Workspace

logger = get_logger("core.project_context")


class ProjectContextGenerator:
    """Generates a natural language project summary."""

    def __init__(self) -> None:
        ws = Workspace.get_instance()
        self._root = ws.get_project_root()
        self._gptcgt_dir = self._root / ".gptcgt"

    def generate(self) -> str:
        """Scan project and return markdown project summary."""
        lang = self._detect_language()
        framework = self._detect_framework()
        test_runner = self._detect_test_runner()
        linter = self._detect_linter()
        structure = self._summarize_structure()

        from src.tools.repo_map import RepoMap

        rm = RepoMap()
        idx = rm.get_index()

        lines = [
            f"# Project: {self._root.name}\n",
            "## Overview",
            f"{lang.get('name', 'Unknown')} project with {idx.total_files} files and {idx.total_lines:,} lines of code.\n",  # noqa: E501
            "## Tech Stack",
            f"- **Language:** {lang.get('name', 'Unknown')} {lang.get('version', '')}".strip(),
        ]
        if framework:
            lines.append(f"- **Framework:** {framework}")
        if test_runner:
            lines.append(f"- **Testing:** {test_runner}")
        if linter:
            lines.append(f"- **Linter:** {linter}")

        lines.extend(["", "## Project Structure"])
        lines.extend(structure)

        return "\n".join(lines)

    def generate_and_save(self) -> Path:
        """Generate and save to .gptcgt/project.md."""
        self._gptcgt_dir.mkdir(parents=True, exist_ok=True)
        content = self.generate()
        path = self._gptcgt_dir / "project.md"
        path.write_text(content, encoding="utf-8")
        logger.info(f"Generated project context: {path}")
        return path

    def _detect_language(self) -> dict:
        """Detect primary language from file extensions."""
        counts: dict[str, int] = {}
        EXCLUDED_DIRS = {
            ".git",
            "node_modules",
            "venv",
            ".venv",
            "__pycache__",
            ".mypy_cache",
            "dist",
            "build",
            ".next",
            "test-env",
            ".gptcgt",
            "tmp",
            ".tox",
            ".pytest_cache",
            "coverage",
            ".ruff_cache",
        }
        for fp in self._root.rglob("*"):
            if any(ex in fp.parts for ex in EXCLUDED_DIRS):
                continue
            if fp.is_file():
                ext = fp.suffix.lower()
                if ext in (".py",):
                    counts["Python"] = counts.get("Python", 0) + 1
                elif ext in (".js", ".jsx"):
                    counts["JavaScript"] = counts.get("JavaScript", 0) + 1
                elif ext in (".ts", ".tsx"):
                    counts["TypeScript"] = counts.get("TypeScript", 0) + 1
                elif ext in (".rs",):
                    counts["Rust"] = counts.get("Rust", 0) + 1
                elif ext in (".go",):
                    counts["Go"] = counts.get("Go", 0) + 1
                elif ext in (".java",):
                    counts["Java"] = counts.get("Java", 0) + 1
        if not counts:
            return {"name": "Unknown"}
        primary = max(counts, key=counts.get)

        version = ""
        if primary == "Python":
            pyproject = self._root / "pyproject.toml"
            if pyproject.exists():
                try:
                    content = pyproject.read_text()
                    import re

                    m = re.search(r'requires-python\s*=\s*"([^"]+)"', content)
                    if m:
                        version = m.group(1)
                except Exception:
                    pass
        return {"name": primary, "version": version}

    def _detect_framework(self) -> str | None:
        """Detect framework from dependency files."""
        frameworks = []
        # Python
        for dep_file in ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"]:
            path = self._root / dep_file
            if path.exists():
                try:
                    content = path.read_text().lower()
                    if "fastapi" in content:
                        frameworks.append("FastAPI")
                    elif "django" in content:
                        frameworks.append("Django")
                    elif "flask" in content:
                        frameworks.append("Flask")
                except Exception:
                    pass
        # JS/TS
        pkg = self._root / "package.json"
        if pkg.exists():
            try:
                content = pkg.read_text().lower()
                if "next" in content:
                    frameworks.append("Next.js")
                elif "react" in content:
                    frameworks.append("React")
                elif "vue" in content:
                    frameworks.append("Vue")
                elif "express" in content:
                    frameworks.append("Express")
            except Exception:
                pass
        # Rust
        cargo = self._root / "Cargo.toml"
        if cargo.exists():
            try:
                content = cargo.read_text().lower()
                if "actix" in content:
                    frameworks.append("Actix")
                elif "axum" in content:
                    frameworks.append("Axum")
                elif "rocket" in content:
                    frameworks.append("Rocket")
            except Exception:
                pass
        return ", ".join(frameworks) if frameworks else None

    def _detect_test_runner(self) -> str | None:
        if (self._root / "pytest.ini").exists() or (self._root / "conftest.py").exists():
            return "pytest"
        if (self._root / "jest.config.js").exists() or (self._root / "jest.config.ts").exists():
            return "Jest"
        pkg = self._root / "package.json"
        if pkg.exists():
            try:
                if "vitest" in pkg.read_text().lower():
                    return "Vitest"
                if "jest" in pkg.read_text().lower():
                    return "Jest"
            except Exception:
                pass
        # Check pyproject.toml
        pp = self._root / "pyproject.toml"
        if pp.exists():
            try:
                if "pytest" in pp.read_text().lower():
                    return "pytest"
            except Exception:
                pass
        return None

    def _detect_linter(self) -> str | None:
        linters = []
        if (self._root / "ruff.toml").exists() or (self._root / ".ruff.toml").exists():
            linters.append("ruff")
        if (self._root / ".eslintrc.js").exists() or (self._root / ".eslintrc.json").exists():
            linters.append("ESLint")
        pp = self._root / "pyproject.toml"
        if pp.exists():
            try:
                content = pp.read_text().lower()
                if "ruff" in content and "ruff" not in linters:
                    linters.append("ruff")
                if "mypy" in content:
                    linters.append("mypy")
            except Exception:
                pass
        return ", ".join(linters) if linters else None

    def _summarize_structure(self) -> list[str]:
        """Summarize top-level directory purposes."""
        lines = []
        for item in sorted(self._root.iterdir()):
            if item.name.startswith(".") or item.name in (
                "node_modules",
                "__pycache__",
                "venv",
                ".venv",
            ):
                continue
            if item.is_dir():
                EXCLUDED_DIRS = {
                    ".git",
                    "node_modules",
                    "venv",
                    ".venv",
                    "__pycache__",
                    ".mypy_cache",
                    "dist",
                    "build",
                    ".next",
                }
                file_count = sum(
                    1 for _ in item.rglob("*") if _.is_file() and not any(ex in _.parts for ex in EXCLUDED_DIRS)
                )
                lines.append(f"- `{item.name}/` — {file_count} files")
            elif item.is_file() and item.name in (
                "README.md",
                "pyproject.toml",
                "package.json",
                "Cargo.toml",
                "Makefile",
            ):
                lines.append(f"- `{item.name}` — project config")
        return lines
