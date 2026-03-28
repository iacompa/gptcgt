#!/usr/bin/env python3
"""Repository health checks for dead imports, duplicate files, and runtime contracts."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv-audit", ".venv", ".next", ".ruff_cache", "__pycache__", ".pytest_cache", "node_modules"}


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str | None = None


def _collect_duplicate_files() -> list[str]:
    duplicates: list[str] = []
    suffix_re = re.compile(r"^(?P<base>.+?)\s+2(?P<ext>\.[^.]+)$")
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue

        match = suffix_re.match(path.name)
        if not match:
            continue

        base_name = f"{match.group('base')}{match.group('ext')}"
        candidate = path.with_name(base_name)
        if candidate.exists():
            duplicates.append(f"{path} (sibling: {candidate})")

    return sorted(duplicates)


def _run_command(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> CheckResult:
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True)
    ok = proc.returncode == 0
    details = proc.stdout.strip() or proc.stderr.strip()
    return CheckResult(name=" ".join(cmd), ok=ok, detail=details or None)


def _ruff_imports_check() -> CheckResult:
    return _run_command(
        [sys.executable, "-m", "ruff", "check", "src", "api", "tests", "scripts", "--select", "F401"],
        cwd=ROOT,
    )


def _pytest_core_edge_cases() -> CheckResult:
    edge_tests = [
        "tests/test_arbiter_edge_cases.py",
        "tests/test_chat_pipeline_edge_cases.py",
        "tests/test_parallel_dispatcher_edge_cases.py",
    ]
    return _run_command([sys.executable, "-m", "pytest", *edge_tests], cwd=ROOT)


def _npm_lint_strict() -> CheckResult:
    next_bin = ROOT / "web" / "node_modules" / ".bin" / "next"
    if not next_bin.exists():
        return CheckResult(
            name="npm:lint:strict",
            ok=False,
            detail=(
                "Next.js dependencies are not installed for web/. "
                "Run `npm --prefix web ci` and re-run this check."
            ),
        )
    return _run_command(["npm", "run", "lint:strict"], cwd=ROOT / "web")


def _run_contract_tests_if_available() -> CheckResult | None:
    if not (os.getenv("CONTRACT_BASE_URL") or os.getenv("NEXT_PUBLIC_BASE_URL") or os.getenv("BASE_URL")):
        return None

    return _run_command(["npm", "run", "test:contracts"], cwd=ROOT / "web")


def _build_duplicate_report(duplicates: list[str]) -> CheckResult:
    if duplicates:
        return CheckResult(
            name="duplicate-file-policy",
            ok=False,
            detail="Duplicate filename pattern detected:\\n" + "\\n".join(duplicates),
        )
    return CheckResult(name="duplicate-file-policy", ok=True)


def main() -> int:
    checks: list[CheckResult] = []
    checks.append(_ruff_imports_check())
    checks.append(_build_duplicate_report(_collect_duplicate_files()))
    checks.append(_npm_lint_strict())
    checks.append(_pytest_core_edge_cases())

    contract_check = _run_contract_tests_if_available()
    if contract_check is not None:
        checks.append(contract_check)

    failures = [check for check in checks if not check.ok]
    for check in checks:
        print(f"[{check.name}] {'PASS' if check.ok else 'FAIL'}")
        if check.detail:
            print(check.detail)

    if failures:
        print(f"Verification failed: {len(failures)} failed check(s).")
        return 1

    print("Verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
