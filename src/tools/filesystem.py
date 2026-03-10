"""
Filesystem tools for AI agents. Agents call these via LLM tool_use
to explore the codebase. All operations sandboxed within Workspace.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from src.core.logger import get_logger
from src.core.workspace import Workspace

logger = get_logger("tools.filesystem")


def _should_skip(path: Path, root: Path) -> bool:
    SKIP = {
        ".git",
        ".gptcgt",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        "target",
    }
    for part in path.relative_to(root).parts:
        if part in SKIP:
            return True
    return False


def glob_files(pattern: str, max_results: int = 50) -> list[dict]:
    """Find files matching a glob pattern within workspace."""
    ws = Workspace.get_instance()
    results = []
    if ".." in Path(pattern).parts:
        return [{"error": "Pattern cannot contain parent directory references (..)"}]

    try:
        for fp in sorted(ws.get_project_root().glob(pattern)):
            try:
                ws.validate_path(str(fp))
            except Exception:
                continue

            if not fp.is_file() or _should_skip(fp, ws.get_project_root()):
                continue
            rel = str(fp.relative_to(ws.get_project_root()))
            try:
                size = fp.stat().st_size
                lines = fp.read_text(encoding="utf-8", errors="replace").count("\n") + 1
                results.append({"path": rel, "size_bytes": size, "lines": lines})
            except Exception:
                results.append({"path": rel, "size_bytes": 0, "lines": 0})
            if len(results) >= max_results:
                break
    except Exception as e:
        return [{"error": str(e)}]
    return results


def grep_search(query: str, path: str = "", max_results: int = 30, case_sensitive: bool = False) -> list[dict]:
    """Search file contents for a text pattern within workspace."""
    ws = Workspace.get_instance()
    search_dir = ws.get_project_root() / path if path else ws.get_project_root()
    try:
        ws.validate_path(str(search_dir))
    except Exception:
        return [{"error": "Search path outside workspace"}]

    results = []
    # Try native grep first (faster)
    if sys.platform != "win32":
        try:
            args = ["grep", "-rn"]
            if not case_sensitive:
                args.append("-i")
            args.extend(["-m", str(max_results * 2)])
            for e in [
                "py",
                "js",
                "ts",
                "tsx",
                "jsx",
                "rs",
                "go",
                "java",
                "c",
                "h",
                "cpp",
                "rb",
                "md",
                "toml",
                "yaml",
                "yml",
                "json",
            ]:
                args.append(f"--include=*.{e}")
            args.extend(["--", query, str(search_dir)])
            proc = subprocess.run(args, capture_output=True, text=True, timeout=10, cwd=str(ws.get_project_root()))
            for line in proc.stdout.splitlines()[:max_results]:
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    try:
                        rel = str(Path(parts[0]).relative_to(ws.get_project_root()))
                    except ValueError:
                        rel = parts[0]
                    if not _should_skip(Path(parts[0]), ws.get_project_root()):
                        results.append({"file": rel, "line": int(parts[1]), "content": parts[2].strip()[:200]})
            return results[:max_results]
        except Exception:
            pass

    # Python fallback
    q = query.lower() if not case_sensitive else query
    for fp in search_dir.rglob("*"):
        if not fp.is_file() or _should_skip(fp, ws.get_project_root()) or fp.stat().st_size > 500_000:
            continue
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(content.splitlines(), 1):
                cmp = line.lower() if not case_sensitive else line
                if q in cmp:
                    results.append(
                        {
                            "file": str(fp.relative_to(ws.get_project_root())),
                            "line": i,
                            "content": line.strip()[:200],
                        }
                    )
                    if len(results) >= max_results:
                        return results
        except Exception:
            continue
    return results


def read_file(path: str, start_line: int | None = None, end_line: int | None = None) -> str:
    """Read a file or line range within workspace. Returns content with line numbers."""
    ws = Workspace.get_instance()
    try:
        content = ws.safe_read(path)
    except Exception as e:
        return f"Error reading {path}: {e}"

    lines = content.splitlines()
    total = len(lines)
    s = max(0, (start_line or 1) - 1)
    e = min(total, end_line or total)
    w = len(str(e))

    header = f"# {path} ({total} lines total)"
    if start_line or end_line:
        header += f" — showing lines {s + 1}-{e}"
    formatted = "\n".join(f"{i + 1:>{w}} | {lines[i]}" for i in range(s, e))
    return f"{header}\n{formatted}"
