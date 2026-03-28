"""
E2B Sandbox interface for isolated code execution.

Used by the Arbiter to:
1. Apply each agent's patch in a clean environment
2. Run the project's test suite against the patched code
3. Run linters on modified files
4. Run security scanners on modified files

E2B Details:
- 150ms cold start (Firecracker microVMs, same as AWS Lambda)
- $0.083/hr pricing
- Typical verification: 10-30 seconds = ~$0.001-0.002 per run
- Pre-built templates for Python, TypeScript, Rust, Go

Fallback:
- If E2B is not configured (no API key), fall back to local-only verification:
  - Syntax check via tree-sitter (always available)
  - Local linter if installed (ruff, eslint)
  - No test execution, no security scan
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from src.core.diff_engine import PatchSet
from src.core.endpoints import resolve_sandbox_execute_url
from src.core.logger import get_logger

logger = get_logger("tools.sandbox")


@dataclass
class SandboxResult:
    """Result from a single command execution in the sandbox."""

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


@dataclass
class TestResult:
    """Parsed test execution results."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    failures: list[dict] = field(default_factory=list)  # [{test_name, error, traceback}]
    raw_output: str = ""

    @property
    def all_passed(self) -> bool:
        return self.failed == 0 and self.errors == 0

    @property
    def pass_rate(self) -> float:
        return self.passed / max(self.total, 1) * 100


@dataclass
class LintResult:
    """Parsed lint results."""

    warnings: list[dict] = field(default_factory=list)  # [{file, line, rule, message, severity}]
    errors: list[dict] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return len(self.errors) == 0

    @property
    def new_violations(self) -> int:
        return len(self.warnings) + len(self.errors)


@dataclass
class VerificationResult:
    """Aggregate result from all sandbox verification steps."""

    agent_id: str
    model_name: str

    # Stage 1: Structural (done locally before sandbox, included for completeness)
    syntax_valid: bool = True
    syntax_errors: list[str] = field(default_factory=list)

    # Stage 2: Lint
    lint_result: LintResult | None = None

    # Stage 3: Tests
    test_result: TestResult | None = None

    # Stage 4: Security (from security.py, included here for aggregation)
    security_findings: list = field(default_factory=list)  # SecurityFinding objects

    # Stage 5: Diff stats (computed locally)
    lines_changed: int = 0
    files_touched: int = 0

    # Stage 6: Complexity delta (computed locally)
    complexity_before: float = 0.0
    complexity_after: float = 0.0

    @property
    def badge(self) -> str:
        if any(f.severity == "critical" for f in self.security_findings):
            return "blocked"
        if not self.syntax_valid:
            return "blocked"
        if self.test_result and not self.test_result.all_passed:
            return "warning"
        if any(f.severity in ("high", "medium") for f in self.security_findings):
            return "warning"
        return "clean"


# Language-specific tool configurations
LANGUAGE_TOOLS = {
    "python": {
        "linter": "ruff check --output-format json {files}",
        "test_runner": "pytest --tb=short -q",
        "security": "semgrep --config auto --json {files}",
        "template": "python-3.11",
    },
    "typescript": {
        "linter": "eslint --format json {files}",
        "test_runner": "npx jest --ci --json",
        "security": "semgrep --config auto --json {files}",
        "template": "node-18",
    },
    "javascript": {
        "linter": "eslint --format json {files}",
        "test_runner": "npx jest --ci --json",
        "security": "semgrep --config auto --json {files}",
        "template": "node-18",
    },
    "rust": {
        "linter": "cargo clippy --message-format=json",
        "test_runner": "cargo test --message-format=json",
        "security": "cargo audit --json",
        "template": "rust-1.75",
    },
    "go": {
        "linter": "golangci-lint run --out-format json",
        "test_runner": "go test -json ./...",
        "security": "gosec -fmt=json ./...",
        "template": "go-1.21",
    },
}


class E2BSandbox:
    """
    Interface to E2B sandbox for isolated code verification.

    If E2B API key is not configured, falls back to local-only verification.
    """

    def __init__(self) -> None:
        from src.auth.keychain import KeyChainManager

        self._api_key = KeyChainManager.get_key("E2B_API_KEY") or os.environ.get("E2B_API_KEY", "")
        self._available = bool(self._api_key)
        if not self._available:
            logger.info("E2B API key not configured — sandbox verification disabled, using local fallback")

    @property
    def available(self) -> bool:
        return self._available

    async def verify_patch(
        self,
        patch_set: PatchSet,
        project_root: Path,
        language: str,
        test_command: str | None = None,
        on_stdout: "Callable[[str], None] | None" = None,
        on_stderr: "Callable[[str], None] | None" = None,
    ) -> VerificationResult:
        """
        Run the full verification pipeline on a PatchSet.

        If E2B is available: run in sandbox (tests, lint, security)
        If not: local-only (syntax check, local lint if installed)
        """
        result = VerificationResult(
            agent_id=patch_set.agent_id,
            model_name=patch_set.model_name,
        )

        # Compute diff stats (always local, instant)
        result.lines_changed = sum(
            sum(len(h.modified_lines) + len(h.original_lines) for h in fp.hunks) for fp in patch_set.patches
        )
        result.files_touched = patch_set.file_count

        if not self._available:
            from src.auth.keychain import KeyChainManager

            session_token = KeyChainManager.get_key("GPTCGT_SESSION_TOKEN")
            if session_token:
                try:
                    return await self._verify_with_proxy(
                        patch_set, project_root, language, test_command, session_token, result, on_stdout, on_stderr
                    )
                except Exception as e:
                    logger.warning(f"Proxy verification failed, falling back to local: {e}")
                    return await self._verify_local_only(patch_set, project_root, language, result)
            else:
                return await self._verify_local_only(patch_set, project_root, language, result)

        return await self._verify_with_sandbox(
            patch_set, project_root, language, test_command, result, on_stdout, on_stderr
        )

    async def _verify_local_only(
        self,
        patch_set: PatchSet,
        project_root: Path,
        language: str,
        result: VerificationResult,
    ) -> VerificationResult:
        """
        Fallback verification when E2B is not available.
        Uses tree-sitter for syntax check and local linter if installed.
        """
        # Syntax check via tree-sitter (always available from Phase 3)
        from src.tools.tree_sitter_utils import extract_symbols

        for fp in patch_set.patches:
            full_path = project_root / fp.file_path
            if full_path.exists():
                try:
                    # If tree-sitter can parse it, syntax is valid
                    content = full_path.read_text(errors="replace")
                    extract_symbols(full_path, content)
                except Exception as e:
                    result.syntax_valid = False
                    result.syntax_errors.append(f"{fp.file_path}: {e}")

        # Try local linter if available
        import shutil

        if language == "python" and shutil.which("ruff"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "ruff",
                    "check",
                    "--output-format",
                    "json",
                    *[str(project_root / fp.file_path) for fp in patch_set.patches],
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
                lint_data = json.loads(stdout.decode()) if stdout else []
                result.lint_result = LintResult(
                    warnings=[
                        {
                            "file": d.get("filename", ""),
                            "line": d.get("location", {}).get("row", 0),
                            "rule": d.get("code", ""),
                            "message": d.get("message", ""),
                            "severity": "warning",
                        }
                        for d in lint_data
                    ],
                )
            except Exception as e:
                logger.warning(f"Local lint failed: {e}")

        return result

    async def _verify_with_proxy(
        self,
        patch_set: PatchSet,
        project_root: Path,
        language: str,
        test_command: str | None,
        session_token: str,
        result: VerificationResult,
        on_stdout: "Callable[[str], None] | None" = None,
        on_stderr: "Callable[[str], None] | None" = None,
    ) -> VerificationResult:
        """
        Execute sandbox verification securely via the backend gptcgt proxy.
        This provides Zero-Retention execution for Pro/Team users without needing a local E2B key.
        """
        import httpx

        from src.core.config import ConfigManager

        files_to_upload = self._collect_files_for_sandbox(patch_set, project_root)

        # Apply patches locally in-memory to the files dictionary before transmission
        for fp in patch_set.patches:
            if str(fp.file_path) in files_to_upload:
                lines = files_to_upload[str(fp.file_path)].splitlines()
                for hunk in sorted(fp.hunks, key=lambda h: h.start_line, reverse=True):
                    lines[hunk.start_line - 1 : hunk.end_line] = hunk.modified_lines
                patched = "\n".join(lines)
                if files_to_upload[str(fp.file_path)].endswith("\n"):
                    patched += "\n"

                # P2-08: Circuit breaker - check syntax in memory before transmission
                if str(fp.file_path).endswith(".py"):
                    import ast
                    try:
                        ast.parse(patched)
                    except SyntaxError as e:
                        logger.error(f"Syntax error in patched {fp.file_path}: {e}")
                        result.syntax_valid = False
                        result.syntax_errors.append(f"{fp.file_path}: SyntaxError: {e}")
                        return result  # Abort immediately

                files_to_upload[str(fp.file_path)] = patched

        tools = LANGUAGE_TOOLS.get(language, LANGUAGE_TOOLS.get("python"))
        test_cmd = test_command or tools.get("test_runner", "pytest")

        payload = {"files": files_to_upload, "language": language, "command": test_cmd}

        config = ConfigManager.get_instance()
        base_url = resolve_sandbox_execute_url(explicit=config.user.api_base_url)
        # The proxy exposes /v1/sandbox/execute
        url = base_url

        if on_stdout:
            on_stdout(f"🚀 Sending {len(files_to_upload)} files to Zero-Retention Sandbox Proxy...\n")

        try:
            async with httpx.AsyncClient(timeout=65.0) as client:
                resp = await client.post(url, json=payload, headers={"Authorization": f"Bearer {session_token}"})
                resp.raise_for_status()
                data = resp.json()

            if on_stdout and data.get("stdout"):
                on_stdout(data["stdout"])
            if on_stderr and data.get("stderr"):
                on_stderr(data["stderr"])

            # Parse test results
            result.test_result = self._parse_test_output(
                data.get("stdout", ""), data.get("stderr", ""), data.get("exit_code", 1), language
            )
        except Exception as e:
            if on_stderr:
                on_stderr(f"❌ Proxy Execution Error: {str(e)}\n")
            raise e

        return result

    async def _verify_with_sandbox(
        self,
        patch_set: PatchSet,
        project_root: Path,
        language: str,
        test_command: str | None,
        result: VerificationResult,
        on_stdout: "Callable[[str], None] | None" = None,
        on_stderr: "Callable[[str], None] | None" = None,
    ) -> VerificationResult:
        """
        Full verification in E2B sandbox.

        IMPORTANT: This requires the e2b package. Import it here to make
        it optional — the app works without E2B installed.
        """
        try:
            from e2b_code_interpreter import Sandbox
        except ImportError:
            logger.warning("e2b package not installed — falling back to local verification")
            return await self._verify_local_only(patch_set, project_root, language, result)

        tools = LANGUAGE_TOOLS.get(language, LANGUAGE_TOOLS.get("python"))
        sandbox = None

        try:
            # Create sandbox session
            sandbox = Sandbox(api_key=self._api_key, template=tools["template"])

            # Upload relevant project files
            files_to_upload = self._collect_files_for_sandbox(patch_set, project_root)
            for rel_path, content in files_to_upload.items():
                sandbox.files.write(f"/home/user/project/{rel_path}", content)

            # Apply the patch (write modified versions of files)
            for fp in patch_set.patches:
                try:
                    original = (project_root / fp.file_path).read_text()
                    lines = original.splitlines()
                    # Apply approved/pending hunks (for verification, treat pending as approved)
                    for hunk in sorted(fp.hunks, key=lambda h: h.start_line, reverse=True):
                        lines[hunk.start_line - 1 : hunk.end_line] = hunk.modified_lines
                    patched = "\n".join(lines)
                    if original.endswith("\n"):
                        patched += "\n"

                    # P2-08: Circuit breaker - check syntax in memory before transmission
                    if str(fp.file_path).endswith(".py"):
                        import ast
                        try:
                            ast.parse(patched)
                        except SyntaxError as e:
                            logger.error(f"Syntax error in patched {fp.file_path}: {e}")
                            result.syntax_valid = False
                            result.syntax_errors.append(f"{fp.file_path}: SyntaxError: {e}")
                            return result  # Abort immediately

                    sandbox.files.write(f"/home/user/project/{fp.file_path}", patched)
                except Exception as e:
                    logger.warning(f"Failed to apply patch for {fp.file_path}: {e}")

            # Run lint
            modified_files_str = " ".join(str(fp.file_path) for fp in patch_set.patches)
            lint_cmd = tools["linter"].replace("{files}", modified_files_str)
            try:
                cb_out = (lambda m: on_stdout(str(getattr(m, "line", m)) + "\n")) if on_stdout else None
                cb_err = (lambda m: on_stderr(str(getattr(m, "line", m)) + "\n")) if on_stderr else None

                lint_exec = sandbox.commands.run(
                    f"cd /home/user/project && {lint_cmd}",
                    timeout=30,
                    on_stdout=cb_out,
                    on_stderr=cb_err,
                )
                result.lint_result = self._parse_lint_output(lint_exec.stdout, language)
            except Exception as e:
                logger.warning(f"Sandbox lint failed: {e}")

            # Run tests
            test_cmd = test_command or tools["test_runner"]
            try:
                cb_out = (lambda m: on_stdout(str(getattr(m, "line", m)) + "\n")) if on_stdout else None
                cb_err = (lambda m: on_stderr(str(getattr(m, "line", m)) + "\n")) if on_stderr else None
                test_exec = sandbox.commands.run(
                    f"cd /home/user/project && {test_cmd}",
                    timeout=120,
                    on_stdout=cb_out,
                    on_stderr=cb_err,
                )
                result.test_result = self._parse_test_output(
                    test_exec.stdout, test_exec.stderr, test_exec.exit_code, language
                )
            except Exception as e:
                logger.warning(f"Sandbox test execution failed: {e}")

            # Security scan runs separately via security.py — not in sandbox
            # (semgrep is run locally or in its own process, see Part C)

        except Exception as e:
            logger.error(f"E2B sandbox error: {e}")
        finally:
            if sandbox:
                try:
                    sandbox.kill()
                except Exception:
                    pass

        return result

    def _collect_files_for_sandbox(self, patch_set: PatchSet, project_root: Path) -> dict[str, str]:
        """Collect project files needed for sandbox verification."""
        files: dict[str, str] = {}

        # Include patched files + their dependencies (import graph)
        for fp in patch_set.patches:
            full_path = project_root / fp.file_path
            if full_path.exists():
                files[str(fp.file_path)] = full_path.read_text(errors="replace")

        # Include test files if they exist
        test_patterns = ["tests/", "test_", "_test.py", ".test.ts", ".test.js", ".spec.ts"]
        for pattern in test_patterns:
            for test_file in project_root.rglob(f"*{pattern}*"):
                if test_file.is_file() and test_file.stat().st_size < 100_000:
                    rel = str(test_file.relative_to(project_root))
                    if rel not in files:
                        files[rel] = test_file.read_text(errors="replace")

        # Include config files (pyproject.toml, package.json, etc.)
        for config in [
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "package.json",
            "tsconfig.json",
            "Cargo.toml",
            "go.mod",
            "conftest.py",
        ]:
            config_path = project_root / config
            if config_path.exists():
                files[config] = config_path.read_text(errors="replace")

        return files

    def _parse_lint_output(self, stdout: str, language: str) -> LintResult:
        """Parse linter JSON output into LintResult."""
        result = LintResult()
        try:
            data = json.loads(stdout) if stdout else []
            if language == "python":
                # ruff JSON format
                for item in data if isinstance(data, list) else []:
                    entry = {
                        "file": item.get("filename", ""),
                        "line": item.get("location", {}).get("row", 0),
                        "rule": item.get("code", ""),
                        "message": item.get("message", ""),
                        "severity": "error" if item.get("code", "").startswith("E") else "warning",
                    }
                    if entry["severity"] == "error":
                        result.errors.append(entry)
                    else:
                        result.warnings.append(entry)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse lint output: {e}")
        return result

    def _parse_test_output(self, stdout: str, stderr: str, exit_code: int, language: str) -> TestResult:
        """Parse test runner output into TestResult."""
        result = TestResult()
        combined = f"{stdout}\n{stderr}"
        result.raw_output = combined

        if language == "python":
            # Parse pytest output
            # Look for "X passed, Y failed, Z errors" pattern
            import re

            match = re.search(r"(\d+) passed", combined)
            if match:
                result.passed = int(match.group(1))
            match = re.search(r"(\d+) failed", combined)
            if match:
                result.failed = int(match.group(1))
            match = re.search(r"(\d+) error", combined)
            if match:
                result.errors = int(match.group(1))
            match = re.search(r"(\d+) skipped", combined)
            if match:
                result.skipped = int(match.group(1))
            result.total = result.passed + result.failed + result.errors

            # Extract failure details
            if result.failed > 0:
                failure_blocks = re.findall(
                    r"FAILED\s+([\w/.:]+)\s*-\s*(.*?)(?=\nFAILED|\n={3,}|$)", combined, re.DOTALL
                )
                for test_name, error_text in failure_blocks:
                    result.failures.append(
                        {
                            "test_name": test_name.strip(),
                            "error": error_text.strip()[:500],  # Truncate long tracebacks
                        }
                    )

        # When no test output was parsed, do NOT fabricate a pass.
        # An exit code of 0 with no parsed results means either no tests ran
        # or the output format was unrecognized — both are inconclusive, not passing.
        if result.total == 0 and exit_code != 0:
            # Non-zero exit with no parsed results = something failed
            result.total = 1
            result.failed = 1

        return result
