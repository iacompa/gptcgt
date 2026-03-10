# ruff: noqa: E501

"""
LSP Client for cross-file reference verification.

After an agent proposes code changes, the LSP verifies that ALL references
to modified symbols have been updated. This catches the #2 developer complaint
about AI coding tools: broken multi-file edits.

Example flow:
    Agent renames process_payment() in payments.py
    → LSP finds references in orders.py:42, checkout.py:18, tests/test_payments.py:7
    → Checks: did the agent update all three?
    → orders.py:42 — UPDATED ✓
    → checkout.py:18 — MISSED ✗
    → Result: incomplete, missed reference at checkout.py:18

LSP servers start on-demand (not at app startup):
- Python: pyright-langserver or pylsp
- TypeScript/JS: typescript-language-server
- Rust: rust-analyzer
- Go: gopls
- Java: jdtls
- C/C++: clangd

If the LSP server for a language is not installed, verification is skipped
gracefully — the agent's output is still presented, just without reference checking.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from src.core.diff_engine import PatchSet
from src.core.logger import get_logger

logger = get_logger("tools.lsp")


@dataclass
class Reference:
    """A location where a symbol is referenced."""

    file_path: Path
    line: int
    character: int
    context: str  # The line content for display


@dataclass
class MissedReference:
    """A reference that was NOT updated by the agent's patch."""

    file_path: Path
    line: int
    symbol_name: str
    context: str  # The original line (with old symbol usage)


@dataclass
class ReferenceVerification:
    """Result of verifying all references for all modified symbols."""

    complete: bool  # True if all references were updated
    total_references: int
    updated_references: int
    missed: list[MissedReference] = field(default_factory=list)
    symbols_checked: list[str] = field(default_factory=list)
    skipped_reason: str | None = None  # If verification was skipped (e.g., no LSP available)


# LSP server configurations per language
LSP_SERVERS: dict[str, dict] = {
    "python": {
        "commands": [
            ["pyright-langserver", "--stdio"],
            ["pylsp"],
        ],
    },
    "typescript": {
        "commands": [
            ["typescript-language-server", "--stdio"],
        ],
    },
    "javascript": {
        "commands": [
            ["typescript-language-server", "--stdio"],
        ],
    },
    "rust": {
        "commands": [
            ["rust-analyzer"],
        ],
    },
    "go": {
        "commands": [
            ["gopls", "serve"],
        ],
    },
}

# LSP message ID counter
_MSG_ID = 0


def _next_id() -> int:
    global _MSG_ID
    _MSG_ID += 1
    return _MSG_ID


class LSPClient:
    """
    Manages LSP server connections for cross-file reference verification.

    Servers start on-demand when needed and are cached per language.
    They auto-shutdown after 5 minutes of inactivity.
    """

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root
        self._servers: dict[str, asyncio.subprocess.Process] = {}
        self._initialized: dict[str, bool] = {}
        self._shutdown_timers: dict[str, asyncio.Task] = {}

    async def verify_patch_references(self, patch_set: PatchSet, language: str) -> ReferenceVerification:
        """
        Verify that all references to modified symbols have been updated.

        1. For each file in the patch, find modified symbols (function/class renames, signature changes)  # noqa: E501
        2. Query LSP "find all references" for each modified symbol
        3. Check if each reference site is also included in the patch
        4. Report missed references
        """
        result = ReferenceVerification(complete=True, total_references=0, updated_references=0)

        # Check if LSP is available for this language
        if language not in LSP_SERVERS:
            result.skipped_reason = f"No LSP configuration for {language}"
            return result

        # Try to start LSP server
        if not await self._ensure_server(language):
            result.skipped_reason = f"LSP server for {language} not available (not installed)"
            return result

        # Collect modified symbols from the patch
        modified_symbols = self._extract_modified_symbols(patch_set)
        if not modified_symbols:
            result.skipped_reason = "No modified symbols detected in patch"
            return result

        result.symbols_checked = list(modified_symbols.keys())

        # Collect all files touched by the patch for quick lookup
        patched_files: set[str] = set()
        patched_lines: dict[str, set[int]] = {}
        for fp in patch_set.patches:
            patched_files.add(str(fp.file_path))
            lines: set[int] = set()
            for hunk in fp.hunks:
                for i in range(len(hunk.modified_lines)):
                    lines.add(hunk.start_line + i)
            patched_lines[str(fp.file_path)] = lines

        # For each modified symbol, find all references and check coverage
        for symbol_name, locations in modified_symbols.items():
            for file_path, line, character in locations:
                refs = await self._find_references(language, file_path, line, character)

                for ref in refs:
                    result.total_references += 1
                    ref_file = str(ref.file_path.relative_to(self._workspace_root))

                    # Check: is this reference in the patch?
                    if ref_file in patched_files:
                        # File is in the patch — check if the specific area was modified
                        if ref_file in patched_lines and ref.line in patched_lines[ref_file]:
                            result.updated_references += 1
                        else:
                            # File is patched but this specific reference wasn't updated
                            result.complete = False
                            result.missed.append(
                                MissedReference(
                                    file_path=ref.file_path,
                                    line=ref.line,
                                    symbol_name=symbol_name,
                                    context=ref.context,
                                )
                            )
                    else:
                        # File is NOT in the patch at all
                        result.complete = False
                        result.missed.append(
                            MissedReference(
                                file_path=ref.file_path,
                                line=ref.line,
                                symbol_name=symbol_name,
                                context=ref.context,
                            )
                        )

        return result

    def _extract_modified_symbols(self, patch_set: PatchSet) -> dict[str, list[tuple[Path, int, int]]]:
        """
        Extract symbols that were modified in the patch.
        Returns {symbol_name: [(file_path, line, character), ...]}

        Heuristic: Look for function/class definitions in removed lines
        that have corresponding definitions in added lines (renames, signature changes).
        """
        import re

        modified: dict[str, list[tuple[Path, int, int]]] = {}

        for fp in patch_set.patches:
            full_path = self._workspace_root / fp.file_path
            for hunk in fp.hunks:
                # Find function/class/method definitions in original lines
                for i, line in enumerate(hunk.original_lines):
                    # Python
                    match = re.match(r"\s*def\s+(\w+)\s*\(", line)
                    if match:
                        symbol = match.group(1)
                        modified.setdefault(symbol, []).append((full_path, hunk.start_line + i, line.index(symbol)))
                        continue
                    match = re.match(r"\s*class\s+(\w+)", line)
                    if match:
                        symbol = match.group(1)
                        modified.setdefault(symbol, []).append((full_path, hunk.start_line + i, line.index(symbol)))
                        continue
                    # TypeScript/JavaScript
                    match = re.match(r"\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)", line)
                    if match:
                        symbol = match.group(1)
                        modified.setdefault(symbol, []).append((full_path, hunk.start_line + i, line.index(symbol)))

        return modified

    async def _ensure_server(self, language: str) -> bool:
        """Ensure LSP server is running for this language. Returns True if available."""
        if language in self._initialized and self._initialized[language]:
            # Reset shutdown timer
            self._reset_shutdown_timer(language)
            return True

        config = LSP_SERVERS.get(language, {})
        commands = config.get("commands", [])

        for cmd in commands:
            if not shutil.which(cmd[0]):
                continue

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                self._servers[language] = proc

                # Send LSP initialize request
                init_result = await self._send_request(
                    language,
                    "initialize",
                    {
                        "processId": os.getpid(),
                        "rootUri": f"file://{self._workspace_root}",
                        "capabilities": {
                            "textDocument": {
                                "references": {"dynamicRegistration": False},
                                "definition": {"dynamicRegistration": False},
                            }
                        },
                    },
                )

                if init_result is not None:
                    # Send initialized notification
                    await self._send_notification(language, "initialized", {})
                    self._initialized[language] = True
                    self._reset_shutdown_timer(language)
                    logger.info(f"LSP server started for {language}: {cmd[0]}")
                    return True
                else:
                    proc.kill()
            except Exception as e:
                logger.warning(f"Failed to start LSP {cmd[0]}: {e}")

        logger.info(f"No LSP server available for {language}")
        return False

    async def _find_references(self, language: str, file_path: Path, line: int, character: int) -> list[Reference]:
        """Query LSP for all references to the symbol at the given position."""
        refs: list[Reference] = []

        try:
            result = await self._send_request(
                language,
                "textDocument/references",
                {
                    "textDocument": {"uri": f"file://{file_path}"},
                    "position": {
                        "line": line - 1,
                        "character": character,
                    },  # LSP uses 0-based lines
                    "context": {"includeDeclaration": False},
                },
            )

            if result and isinstance(result, list):
                for loc in result:
                    uri = loc.get("uri", "")
                    if uri.startswith("file://"):
                        ref_path = Path(uri[7:])
                        ref_line = loc.get("range", {}).get("start", {}).get("line", 0) + 1  # Back to 1-based
                        ref_char = loc.get("range", {}).get("start", {}).get("character", 0)

                        # Read the context line
                        context = ""
                        try:
                            content = ref_path.read_text(errors="replace")
                            lines = content.splitlines()
                            if 0 < ref_line <= len(lines):
                                context = lines[ref_line - 1].strip()
                        except Exception:
                            pass

                        refs.append(
                            Reference(
                                file_path=ref_path,
                                line=ref_line,
                                character=ref_char,
                                context=context,
                            )
                        )
        except Exception as e:
            logger.warning(f"LSP find_references failed: {e}")

        return refs

    async def _send_request(self, language: str, method: str, params: dict) -> dict | list | None:
        """Send a JSON-RPC request to the LSP server and wait for response."""
        proc = self._servers.get(language)
        if not proc or not proc.stdin or not proc.stdout:
            return None

        msg_id = _next_id()
        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "method": method,
                "params": params,
            }
        )
        body_bytes = body.encode("utf-8")
        header = f"Content-Length: {len(body_bytes)}\r\n\r\n"

        proc.stdin.write(header.encode("utf-8") + body_bytes)
        await proc.stdin.drain()

        try:
            # wait_for since asyncio.timeout is 3.11+, and text environments might not support it reliably, we'll keep wait_for  # noqa: E501
            async def _wait_for_message():
                while True:
                    response = await self._read_lsp_message(proc.stdout)
                    if not response:
                        return None
                    if response.get("id") == msg_id:
                        if "error" in response:
                            logger.warning(f"LSP Error: {response['error']}")
                        return response.get("result")

            return await asyncio.wait_for(_wait_for_message(), timeout=30)
        except asyncio.TimeoutError:
            logger.warning(f"LSP request {method} timed out")

        return None

    async def _send_notification(self, language: str, method: str, params: dict) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        proc = self._servers.get(language)
        if not proc or not proc.stdin:
            return

        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            }
        )
        body_bytes = body.encode("utf-8")
        header = f"Content-Length: {len(body_bytes)}\r\n\r\n"
        proc.stdin.write(header.encode("utf-8") + body_bytes)
        await proc.stdin.drain()

    async def _read_lsp_message(self, reader: asyncio.StreamReader) -> dict | None:
        """Read one LSP message from the server's stdout."""
        try:
            # Read headers
            headers = {}
            while True:
                line = await reader.readline()
                line_str = line.decode().strip()
                if not line_str:
                    break
                if ":" in line_str:
                    key, value = line_str.split(":", 1)
                    headers[key.strip()] = value.strip()

            content_length = int(headers.get("Content-Length", 0))
            if content_length > 0:
                body = await reader.readexactly(content_length)
                return json.loads(body.decode())
        except Exception as e:
            logger.warning(f"Failed to read LSP message: {e}")

        return None

    def _reset_shutdown_timer(self, language: str) -> None:
        """Reset the auto-shutdown timer for an LSP server."""
        if language in self._shutdown_timers:
            self._shutdown_timers[language].cancel()
        self._shutdown_timers[language] = asyncio.create_task(
            self._auto_shutdown(language, timeout=300)  # 5 minutes
        )

    async def _auto_shutdown(self, language: str, timeout: int) -> None:
        """Shut down an LSP server after inactivity."""
        await asyncio.sleep(timeout)
        await self._shutdown_server(language)

    async def _shutdown_server(self, language: str) -> None:
        """Shut down a specific LSP server."""
        if language in self._servers:
            try:
                await self._send_request(language, "shutdown", {})
                await self._send_notification(language, "exit", {})
                self._servers[language].kill()
            except Exception:
                pass
            del self._servers[language]
            self._initialized[language] = False
            logger.info(f"LSP server shut down for {language}")

    async def shutdown_all(self) -> None:
        """Shut down all LSP servers. Call on app exit."""
        for language in list(self._servers.keys()):
            await self._shutdown_server(language)
        for timer in self._shutdown_timers.values():
            timer.cancel()

    def format_missed_references(self, verification: ReferenceVerification) -> str:
        """Format missed references for display in narration."""
        if verification.complete:
            return f"✅ All {verification.total_references} references verified"

        if verification.skipped_reason:
            return f"⏭️ LSP verification skipped: {verification.skipped_reason}"

        lines = [
            f"⚠️ {len(verification.missed)} missed reference(s) out of {verification.total_references}:"  # noqa: E501
        ]
        for ref in verification.missed[:5]:
            rel_path = ref.file_path
            try:
                rel_path = ref.file_path.relative_to(self._workspace_root)
            except ValueError:
                pass
            lines.append(f"  ✗ {rel_path}:{ref.line} — {ref.symbol_name}: {ref.context}")

        if len(verification.missed) > 5:
            lines.append(f"  ... and {len(verification.missed) - 5} more")

        return "\n".join(lines)
