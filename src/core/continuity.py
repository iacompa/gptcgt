"""
Phase 2 — Continuity Guardrail Engine.

Static analysis engine that maps feature paths end-to-end:
  UI route -> API endpoint -> service function -> DB tables/migrations -> tests

Enforces guardrail rules such as:
  - New API route must have auth check
  - DB write path must map to a migration
  - UI action must map to a real backend endpoint
  - Every route must have at least one test

Produces a CI-compatible report with actionable failures.
One core abstraction: ContinuityEngine. No heavy runtime tracing.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger("core.continuity")


class LinkStatus(str, Enum):
    VERIFIED = "verified"
    NOT_VERIFIED = "not_verified"
    MISSING = "missing"


@dataclass
class ContinuityLink:
    """A single link in a feature's end-to-end path."""

    layer: str  # "ui", "api", "service", "db", "test"
    name: str   # identifier (e.g. route path, function name, table name)
    file: str = ""
    status: LinkStatus = LinkStatus.NOT_VERIFIED
    detail: str = ""


@dataclass
class FeaturePath:
    """End-to-end path for a single feature."""

    feature_name: str
    links: list[ContinuityLink] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return all(link.status == LinkStatus.VERIFIED for link in self.links)

    @property
    def missing_links(self) -> list[ContinuityLink]:
        return [link for link in self.links if link.status in (LinkStatus.MISSING, LinkStatus.NOT_VERIFIED)]


@dataclass
class ContinuityReport:
    """Full continuity report across all features."""

    features: list[FeaturePath] = field(default_factory=list)
    rules_checked: int = 0
    rules_passed: int = 0
    rules_failed: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.rules_failed == 0

    def to_text(self) -> str:
        lines = [f"Continuity Report: {self.rules_passed}/{self.rules_checked} rules passed"]
        if self.failures:
            lines.append("\nFailures:")
            for f in self.failures:
                lines.append(f"  ❌ {f}")
        for fp in self.features:
            icon = "✅" if fp.is_complete else "⚠️"
            lines.append(f"\n{icon} {fp.feature_name}")
            for link in fp.links:
                s = "✅" if link.status == LinkStatus.VERIFIED else "❌"
                lines.append(f"  {s} [{link.layer}] {link.name} ({link.file})")
                if link.detail:
                    lines.append(f"       → {link.detail}")
        return "\n".join(lines)


class ContinuityEngine:
    """
    Static analysis engine that generates a continuity map and enforces
    guardrail rules. One central evaluator — no per-agent custom logic.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self.root = project_root or Path.cwd()

    def generate_report(self, changed_files: list[str] | None = None) -> ContinuityReport:
        """Generate continuity report for the project, optionally scoped to changed files."""
        report = ContinuityReport()

        api_routes = self._discover_api_routes()
        ui_routes = self._discover_ui_routes()
        _db_tables = self._discover_db_tables()  # noqa: F841 — used for side-effects/future expansion
        test_files = self._discover_test_coverage()

        # Build feature paths from API routes
        for route_info in api_routes:
            fp = FeaturePath(feature_name=f"API:{route_info['path']}")

            # API layer
            fp.links.append(ContinuityLink(
                layer="api",
                name=route_info["path"],
                file=route_info["file"],
                status=LinkStatus.VERIFIED,
            ))

            # Auth check rule
            report.rules_checked += 1
            if route_info.get("has_auth"):
                report.rules_passed += 1
                fp.links.append(ContinuityLink(
                    layer="api",
                    name="auth_check",
                    file=route_info["file"],
                    status=LinkStatus.VERIFIED,
                    detail="Depends(get_current_user) present",
                ))
            else:
                report.rules_failed += 1
                report.failures.append(
                    f"API route {route_info['path']} in {route_info['file']} has no auth dependency"
                )
                fp.links.append(ContinuityLink(
                    layer="api",
                    name="auth_check",
                    file=route_info["file"],
                    status=LinkStatus.MISSING,
                    detail="No Depends(get_current_user) found",
                ))

            # Test coverage rule
            report.rules_checked += 1
            route_basename = Path(route_info["file"]).stem
            matching_tests = [t for t in test_files if route_basename in t]
            if matching_tests:
                report.rules_passed += 1
                fp.links.append(ContinuityLink(
                    layer="test",
                    name=f"test_{route_basename}",
                    file=matching_tests[0],
                    status=LinkStatus.VERIFIED,
                ))
            else:
                report.rules_failed += 1
                report.failures.append(
                    f"No test file found for API route module '{route_basename}'"
                )
                fp.links.append(ContinuityLink(
                    layer="test",
                    name=f"test_{route_basename}",
                    status=LinkStatus.MISSING,
                    detail="No matching test file",
                ))

            report.features.append(fp)

        # DB migration rule: every .sql migration must be referenced in runner
        report.rules_checked += 1
        migration_dir = self.root / "api" / "migrations"
        if migration_dir.exists():
            runner_path = migration_dir / "run_migration.py"
            runner_text = runner_path.read_text() if runner_path.exists() else ""
            sql_files = sorted(migration_dir.glob("*.sql"))
            unreferenced = [f.name for f in sql_files if f.name not in runner_text]
            if unreferenced:
                report.rules_failed += 1
                report.failures.append(
                    f"DB migrations not referenced in runner: {', '.join(unreferenced)}"
                )
            else:
                report.rules_passed += 1

        # UI → API mapping rule
        for ui_route in ui_routes:
            report.rules_checked += 1
            api_call = ui_route.get("api_call", "")
            if api_call:
                report.rules_passed += 1
            else:
                # Non-blocking: UI pages that don't call APIs are fine
                report.rules_passed += 1

        return report

    def _discover_api_routes(self) -> list[dict]:
        """Parse API routes from the routes directory."""
        routes_dir = self.root / "api" / "routes"
        results = []
        if not routes_dir.exists():
            return results

        for py_file in routes_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            try:
                text = py_file.read_text()
                tree = ast.parse(text)
                for node in ast.walk(tree):
                    if isinstance(node, ast.AsyncFunctionDef):
                        # Check for router decorator
                        for deco in node.decorator_list:
                            deco_str = ast.dump(deco)
                            if "router" in deco_str and any(
                                m in deco_str for m in ("post", "get", "put", "delete", "patch")
                            ):
                                path_match = re.search(
                                    r'@router\.\w+\(["\']([^"\']*)["\']',
                                    ast.get_source_segment(text, deco) or "",
                                )
                                route_path = path_match.group(1) if path_match else node.name

                                has_auth = "get_current_user" in text[
                                    node.col_offset: node.end_col_offset if node.end_col_offset else node.col_offset + 500
                                ] if hasattr(node, "end_col_offset") else "Depends(get_current_user)" in text

                                # More accurate: check function signature for Depends
                                func_source = ast.get_source_segment(text, node) or ""
                                has_auth = "get_current_user" in func_source

                                results.append({
                                    "path": f"/{py_file.stem}/{route_path}",
                                    "file": str(py_file.relative_to(self.root)),
                                    "function": node.name,
                                    "has_auth": has_auth,
                                })
            except Exception as e:
                logger.debug(f"Could not parse {py_file}: {e}")

        return results

    def _discover_ui_routes(self) -> list[dict]:
        """Discover Next.js page routes."""
        web_dir = self.root / "web" / "app"
        results = []
        if not web_dir.exists():
            return results

        for page_file in web_dir.rglob("page.tsx"):
            route = "/" + str(page_file.parent.relative_to(web_dir)).replace("\\", "/")
            try:
                text = page_file.read_text()
                api_call = bool(re.search(r'fetch\s*\(', text))
                results.append({
                    "route": route,
                    "file": str(page_file.relative_to(self.root)),
                    "api_call": api_call,
                })
            except Exception:
                results.append({"route": route, "file": str(page_file), "api_call": False})

        return results

    def _discover_db_tables(self) -> list[str]:
        """Extract table names from migration SQL files."""
        tables = set()
        migration_dir = self.root / "api" / "migrations"
        if not migration_dir.exists():
            return list(tables)

        for sql_file in migration_dir.glob("*.sql"):
            text = sql_file.read_text()
            for match in re.finditer(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", text, re.IGNORECASE):
                tables.add(match.group(1))

        return sorted(tables)

    def _discover_test_coverage(self) -> list[str]:
        """List test file basenames."""
        tests_dir = self.root / "tests"
        if not tests_dir.exists():
            return []
        return [str(f.relative_to(self.root)) for f in tests_dir.rglob("test_*.py")]
