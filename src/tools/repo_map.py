"""
Project indexer and repo map generator.
Scans project with tree-sitter, extracts symbols/imports, builds dependency graph.
Produces formatted "repo map" string for AI context (~2-5K tokens).
Cached in .gptcgt/index/. Refreshes on /reindex or project open.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from src.core.logger import get_logger
from src.core.workspace import Workspace
from src.tools.tree_sitter_utils import FileSymbols, extract_symbols


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token)."""
    return len(text) // 4


logger = get_logger("tools.repo_map")

SKIP_DIRS = {
    ".git",
    ".gptcgt",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".tox",
    ".eggs",
    ".next",
    ".nuxt",
    "target",
    ".cargo",
    "vendor",
}
INDEXABLE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".rs",
    ".go",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cc",
    ".rb",
}
MAX_FILE_SIZE = 500_000


@dataclass
class DependencyInfo:
    imports_from: list[str] = field(default_factory=list)
    imported_by: list[str] = field(default_factory=list)


@dataclass
class ProjectIndex:
    root: Path = field(default_factory=Path)
    files: dict[str, FileSymbols] = field(default_factory=dict)
    dependencies: dict[str, DependencyInfo] = field(default_factory=dict)
    total_files: int = 0
    total_lines: int = 0
    primary_language: str = "unknown"
    languages: dict[str, int] = field(default_factory=dict)


class RepoMap:
    """Builds and maintains the project index."""

    def __init__(self, workspace: Workspace | None = None) -> None:
        if workspace is None:
            try:
                workspace = Workspace.get_instance()
            except RuntimeError:
                workspace = Workspace(Path.cwd())
        self._root = workspace.get_project_root()
        self._index_dir = self._root / ".gptcgt" / "index"
        self._index: ProjectIndex | None = None
        self._gitignore_patterns: list[str] = []
        self._load_gitignore()

    def _load_gitignore(self) -> None:
        for ignore_file in [self._root / ".gitignore", self._root / ".gptcgtignore"]:
            if ignore_file.exists():
                try:
                    lines = ignore_file.read_text(encoding="utf-8").splitlines()
                    self._gitignore_patterns.extend(ln.strip() for ln in lines if ln.strip() and not ln.startswith("#"))
                except Exception:
                    pass

    def _should_skip(self, path: Path) -> bool:
        for part in path.parts:
            if part in SKIP_DIRS:
                return True
        rel = str(path.relative_to(self._root))
        for pattern in self._gitignore_patterns:
            if pattern.endswith("/") and (rel.startswith(pattern) or f"/{pattern}" in f"/{rel}/"):
                return True
            elif "*" in pattern and path.match(pattern):
                return True
        return False

    def _iter_source_files(self) -> Iterator[Path]:
        for fp in self._root.rglob("*"):
            if fp.is_file() and not self._should_skip(fp) and fp.suffix.lower() in INDEXABLE_EXTENSIONS:
                if fp.stat().st_size <= MAX_FILE_SIZE:
                    yield fp

    def build_index(self) -> ProjectIndex:
        """Full project scan — run in background thread."""
        logger.info(f"Indexing project: {self._root}")
        index = ProjectIndex(root=self._root)
        workspace = Workspace.get_instance()
        lang_counts: dict[str, int] = {}

        for fp in self._iter_source_files():
            rel = str(fp.relative_to(self._root))
            try:
                content = workspace.safe_read(fp)
                symbols = extract_symbols(fp, content)
                index.files[rel] = symbols
                index.total_files += 1
                index.total_lines += symbols.line_count
                if symbols.language != "unknown":
                    lang_counts[symbols.language] = lang_counts.get(symbols.language, 0) + 1
            except Exception as e:
                logger.warning(f"Failed to index {rel}: {e}")

        index.languages = lang_counts
        if lang_counts:
            index.primary_language = max(lang_counts, key=lang_counts.get)

        self._build_dependency_graph(index)
        self._index = index
        self._save_index(index)
        logger.info(f"Index: {index.total_files} files, {index.total_lines} lines, {index.primary_language}")
        return index

    def _build_dependency_graph(self, index: ProjectIndex) -> None:
        module_to_file: dict[str, str] = {}
        for rel in index.files:
            mod = rel.replace("/", ".").replace("\\", ".")
            if mod.endswith(".py"):
                mod = mod[:-3]
            module_to_file[mod] = rel
            base = mod.split(".")[-1]
            if base not in module_to_file:
                module_to_file[base] = rel

        for rel, symbols in index.files.items():
            deps = DependencyInfo()
            for imp in symbols.imports:
                resolved = self._resolve_import(imp, module_to_file)
                if resolved and resolved != rel:
                    deps.imports_from.append(resolved)
            index.dependencies[rel] = deps

        for rel, deps in index.dependencies.items():
            for imp_file in deps.imports_from:
                if imp_file in index.dependencies:
                    index.dependencies[imp_file].imported_by.append(rel)

    def _resolve_import(self, stmt: str, module_to_file: dict[str, str]) -> str | None:
        match = re.match(r"from\s+([\w.]+)\s+import", stmt)
        if match:
            mod = match.group(1)
            if mod in module_to_file:
                return module_to_file[mod]
            parts = mod.split(".")
            for i in range(len(parts), 0, -1):
                prefix = ".".join(parts[:i])
                if prefix in module_to_file:
                    return module_to_file[prefix]
        match = re.match(r"import\s+([\w.]+)", stmt)
        if match and match.group(1) in module_to_file:
            return module_to_file[match.group(1)]
        return None

    def get_index(self) -> ProjectIndex:
        if self._index is None:
            cached = self._load_cached_index()
            self._index = cached if cached else self.build_index()
        return self._index

    def get_formatted_map(self, max_tokens: int = 4000) -> str:
        """Get formatted repo map for AI context (~2-5K tokens)."""
        index = self.get_index()

        lines = [
            f"## Project: {self._root.name} ({index.primary_language})",
            f"## {index.total_files} files, {index.total_lines:,} lines\n",
        ]

        for i, rel in enumerate(sorted(index.files)):
            sym = index.files[rel]
            deps = index.dependencies.get(rel, DependencyInfo())
            lines.append(f"{rel} ({sym.line_count} lines)")
            for cls in sym.classes:
                methods = sym.methods.get(cls, [])
                if methods:
                    lines.append(f"  class {cls}: {', '.join(methods[:10])}")
                else:
                    lines.append(f"  class {cls}")
            for fn in sym.functions[:15]:
                lines.append(f"  def {fn}()")
            if deps.imports_from:
                lines.append(f"  imports: {', '.join(Path(p).stem for p in deps.imports_from[:5])}")
            if deps.imported_by:
                lines.append(f"  used by: {', '.join(Path(p).stem for p in deps.imported_by[:5])}")
            lines.append("")
            if _estimate_tokens("\n".join(lines)) > max_tokens:
                lines[-1] = f"... ({index.total_files} files total, truncated)"
                break
        return "\n".join(lines)

    def find_relevant_files(
        self,
        mentioned_files: list[str],
        mentioned_symbols: list[str] | None = None,
        max_files: int = 15,
    ) -> list[str]:
        """Find files relevant to a task via mentions + dependency expansion + symbol match."""
        index = self.get_index()
        scored: dict[str, float] = {}

        for mentioned in mentioned_files:
            for rel in index.files:
                if mentioned in rel or Path(rel).name == mentioned:
                    scored[rel] = scored.get(rel, 0) + 10.0

        for rel, score in list(scored.items()):
            if score >= 10.0:
                deps = index.dependencies.get(rel, DependencyInfo())
                for imp in deps.imports_from:
                    scored[imp] = scored.get(imp, 0) + 5.0
                for by in deps.imported_by:
                    scored[by] = scored.get(by, 0) + 3.0

        if mentioned_symbols:
            for rel, sym in index.files.items():
                all_sym = sym.classes + sym.functions
                for s in mentioned_symbols:
                    if s in all_sym:
                        scored[rel] = scored.get(rel, 0) + 7.0

        return [p for p, _ in sorted(scored.items(), key=lambda x: x[1], reverse=True)[:max_files]]

    def _save_index(self, index: ProjectIndex) -> None:
        self._index_dir.mkdir(parents=True, exist_ok=True)
        sym_data = {
            rel: {
                "language": s.language,
                "classes": s.classes,
                "functions": s.functions,
                "methods": s.methods,
                "imports": s.imports,
                "line_count": s.line_count,
            }
            for rel, s in index.files.items()
        }
        (self._index_dir / "symbols.json").write_text(json.dumps(sym_data, indent=2), encoding="utf-8")

        deps_data = {
            rel: {"imports_from": d.imports_from, "imported_by": d.imported_by} for rel, d in index.dependencies.items()
        }
        (self._index_dir / "dependencies.json").write_text(json.dumps(deps_data, indent=2), encoding="utf-8")

    def _load_cached_index(self) -> ProjectIndex | None:
        sym_path = self._index_dir / "symbols.json"
        deps_path = self._index_dir / "dependencies.json"
        if not sym_path.exists():
            return None
        try:
            sym_data = json.loads(sym_path.read_text(encoding="utf-8"))
            deps_data = json.loads(deps_path.read_text(encoding="utf-8")) if deps_path.exists() else {}
            index = ProjectIndex(root=self._root)
            lang_counts: dict[str, int] = {}
            for rel, d in sym_data.items():
                index.files[rel] = FileSymbols(
                    path=self._root / rel,
                    language=d["language"],
                    classes=d.get("classes", []),
                    functions=d.get("functions", []),
                    methods=d.get("methods", {}),
                    imports=d.get("imports", []),
                    line_count=d.get("line_count", 0),
                )
                index.total_files += 1
                index.total_lines += d.get("line_count", 0)
                if d["language"] != "unknown":
                    lang_counts[d["language"]] = lang_counts.get(d["language"], 0) + 1
            index.languages = lang_counts
            if lang_counts:
                index.primary_language = max(lang_counts, key=lang_counts.get)
            for rel, d in deps_data.items():
                index.dependencies[rel] = DependencyInfo(d.get("imports_from", []), d.get("imported_by", []))
            return index
        except Exception as e:
            logger.warning(f"Failed to load cached index: {e}")
            return None
