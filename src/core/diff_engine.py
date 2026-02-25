"""
Diff extraction and patch engine. Parses AI output to extract code changes
in unified diff, search/replace, or code block format. Converts all to
a standard PatchSet for the code viewer's approve/reject flow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from src.core.logger import get_logger
from src.core.workspace import Workspace

logger = get_logger("core.diff_engine")


@dataclass
class Hunk:
    start_line: int
    end_line: int
    original_lines: list[str]
    modified_lines: list[str]
    status: str = "pending"  # pending, approved, rejected
    user_edited: bool = False
    user_text: str | None = None


@dataclass
class FilePatch:
    file_path: str
    hunks: list[Hunk] = field(default_factory=list)
    is_new_file: bool = False
    is_deleted: bool = False

    @property
    def pending_count(self) -> int:
        return sum(1 for h in self.hunks if h.status == "pending")

    @property
    def all_decided(self) -> bool:
        return all(h.status != "pending" for h in self.hunks)


@dataclass
class PatchSet:
    patches: list[FilePatch] = field(default_factory=list)
    agent_id: str = ""
    model_name: str = ""
    model_id: str = ""            # e.g. "openai/gpt-4o" — populated by dispatcher
    raw_response: str = ""
    generation_time: float = 0.0  # Wall-clock seconds from dispatch to completion
    cost_usd: float = 0.0         # USD cost of this generation (from AgentSlot)

    @property
    def file_count(self) -> int:
        return len(self.patches)

    @property
    def total_hunks(self) -> int:
        return sum(len(p.hunks) for p in self.patches)

    @property
    def all_decided(self) -> bool:
        return all(p.all_decided for p in self.patches)


@dataclass
class MultiAgentPatchSet:
    """A collection of patch sets from multiple agents for cherry-picking."""

    patch_sets: list[PatchSet] = field(default_factory=list)

    @property
    def agents(self) -> list[str]:
        return [f"{ps.agent_id} ({ps.model_name})" for ps in self.patch_sets]


class DiffExtractor:
    """Extracts patches from AI response text. Tries unified diff first, then search/replace, then code blocks."""  # noqa: E501

    _UNIFIED = re.compile(
        r"^---\s+(?:a/)?(.*?)\s*\n^\+\+\+\s+(?:b/)?(.*?)\s*\n((?:^@@.*@@.*\n(?:^[ +-].*\n?)*)+)",
        re.MULTILINE,
    )
    _HUNK_HDR = re.compile(r"^@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@")
    _SEARCH_REPLACE = re.compile(
        r"<<<<<<+\s*SEARCH\s*\n(.*?)\n={5,}\n(.*?)\n>{5,}\s*REPLACE", re.DOTALL
    )

    def extract(self, text: str, agent_id: str = "", model_name: str = "") -> PatchSet:
        ps = PatchSet(agent_id=agent_id, model_name=model_name, raw_response=text)

        patches = self._extract_unified(text)
        if patches:
            ps.patches = patches
            logger.info(f"Extracted {len(patches)} file(s) from unified diffs")
            return ps

        patches = self._extract_search_replace(text)
        if patches:
            ps.patches = patches
            logger.info(f"Extracted {len(patches)} file(s) from search/replace")
            return ps

        patches = self._extract_code_blocks(text)
        if patches:
            ps.patches = patches
            logger.info(f"Extracted {len(patches)} file(s) from code blocks")
            return ps

        return ps

    def _extract_unified(self, text: str) -> list[FilePatch]:
        patches = []
        for m in self._UNIFIED.finditer(text):
            file_a, file_b, body = m.group(1).strip(), m.group(2).strip(), m.group(3)
            fp = file_b if file_b != "/dev/null" else file_a
            patch = FilePatch(
                file_path=fp,
                is_new_file=(file_a == "/dev/null"),
                is_deleted=(file_b == "/dev/null"),
            )

            hunk_lines = []
            start = 0
            for line in body.splitlines():
                hm = self._HUNK_HDR.match(line)
                if hm:
                    if hunk_lines:
                        h = self._parse_hunk(start, hunk_lines)
                        if h:
                            patch.hunks.append(h)
                    start = int(hm.group(1))
                    hunk_lines = []
                else:
                    hunk_lines.append(line)
            if hunk_lines:
                h = self._parse_hunk(start, hunk_lines)
                if h:
                    patch.hunks.append(h)
            if patch.hunks:
                patches.append(patch)
        return patches

    def _parse_hunk(self, start: int, lines: list[str]) -> Hunk | None:
        orig, mod = [], []
        ln = start
        end = start - 1
        for line in lines:
            if line.startswith("-"):
                orig.append(line[1:])
                end = ln
                ln += 1
            elif line.startswith("+"):
                mod.append(line[1:])
            elif line.startswith(" "):
                orig.append(line[1:])
                mod.append(line[1:])
                end = ln
                ln += 1
        if not orig and not mod:
            return None
        return Hunk(
            start_line=start, end_line=max(end, start - 1), original_lines=orig, modified_lines=mod
        )

    def _extract_search_replace(self, text: str) -> list[FilePatch]:
        patches_by_file: dict[str, FilePatch] = {}
        for m in self._SEARCH_REPLACE.finditer(text):
            search, replace = m.group(1), m.group(2)
            fp = self._find_file_before(text[: m.start()])
            if not fp:
                continue
            if fp not in patches_by_file:
                patches_by_file[fp] = FilePatch(file_path=fp)
            try:
                ws = Workspace.get_instance()
                file_lines = ws.safe_read(fp).splitlines()
                search_lines = search.splitlines()
                start = self._find_in_lines(file_lines, search_lines)
                if start is not None:
                    patches_by_file[fp].hunks.append(
                        Hunk(
                            start_line=start,
                            end_line=start + len(search_lines) - 1,
                            original_lines=search_lines,
                            modified_lines=replace.splitlines(),
                        )
                    )
            except Exception:
                pass
        return list(patches_by_file.values())

    def _extract_code_blocks(self, text: str) -> list[FilePatch]:
        """Extract fenced code blocks with file paths."""
        pattern = re.compile(r"```\w*\n(?:#\s*([\w./\-]+\.\w+)\n)?(.*?)```", re.DOTALL)
        patches = []
        for m in pattern.finditer(text):
            fp = m.group(1) or self._find_file_before(text[: m.start()])
            if not fp:
                continue
            code = m.group(2).strip()
            ws = Workspace.get_instance()
            try:
                existing = ws.safe_read(fp).splitlines()
                new = code.splitlines()
                if existing != new:
                    patches.append(
                        FilePatch(
                            file_path=fp,
                            hunks=[
                                Hunk(
                                    start_line=1,
                                    end_line=len(existing),
                                    original_lines=existing,
                                    modified_lines=new,
                                )
                            ],
                        )
                    )
            except Exception:
                patches.append(
                    FilePatch(
                        file_path=fp,
                        is_new_file=True,
                        hunks=[
                            Hunk(
                                start_line=1,
                                end_line=1,
                                original_lines=[],
                                modified_lines=code.splitlines(),
                            )
                        ],
                    )
                )
        return patches

    def _find_file_before(self, text: str) -> str | None:
        search = text[-300:] if len(text) > 300 else text
        for pat in [
            r"`([\w./\-]+\.\w+)`\s*$",
            r"([\w./\-]+\.(?:py|js|ts|rs|go|java|c|cpp))\s*:?\s*$",
        ]:
            m = re.search(pat, search, re.MULTILINE)
            if m:
                return m.group(1)
        return None

    def _find_in_lines(self, file_lines: list[str], search: list[str]) -> int | None:
        if not search:
            return None
        stripped = [ln.strip() for ln in search]
        for i in range(len(file_lines) - len(search) + 1):
            if [file_lines[i + j].strip() for j in range(len(search))] == stripped:
                return i + 1
        return None


class PatchEngine:
    """Applies approved patches to disk."""

    def apply_multi_approved(self, multi_ps: MultiAgentPatchSet) -> list[str]:
        """Apply approved hunks from across multiple agents' patch sets."""
        modified = []
        for ps in multi_ps.patch_sets:
            modified.extend(self.apply_approved(ps))
        return list(set(modified))

    def apply_approved(self, patch_set: PatchSet) -> list[str]:
        """Apply all approved hunks in a patch set to the workspace."""
        ws = Workspace.get_instance()
        modified_files = []

        for fp in patch_set.patches:
            approved_hunks = [h for h in fp.hunks if h.status == "approved"]
            if not approved_hunks:
                continue

            if fp.is_new_file:
                # Write a new file entirely from the first approved hunk
                path = Path(ws.get_project_root()) / fp.file_path
                path.parent.mkdir(parents=True, exist_ok=True)
                first_hunk = approved_hunks[0]
                if first_hunk.user_edited and first_hunk.user_text is not None:
                    content = first_hunk.user_text
                else:
                    content = "\n".join(first_hunk.modified_lines)
                ws.safe_write(fp.file_path, content)
                modified_files.append(fp.file_path)
                continue

            if fp.is_deleted:
                # Delete the specific file
                path = Path(ws.get_project_root()) / fp.file_path
                if path.exists():
                    path.unlink()
                    modified_files.append(fp.file_path)
                continue

            # Standard patch process for existing files
            try:
                content = ws.safe_read(fp.file_path)
                lines = content.splitlines()

                # Apply hunks from bottom to top so line numbers remain stable
                for hunk in sorted(approved_hunks, key=lambda h: h.start_line, reverse=True):
                    if hunk.user_edited and hunk.user_text is not None:
                        replacement = hunk.user_text.splitlines()
                    else:
                        replacement = hunk.modified_lines
                    lines[hunk.start_line - 1 : hunk.end_line] = replacement

                new_content = "\n".join(lines)
                if content.endswith("\n"):
                    new_content += "\n"

                ws.safe_write(fp.file_path, new_content)
                modified_files.append(fp.file_path)
            except Exception as e:
                logger.error(f"Failed to apply patch to {fp.file_path}: {e}")

        return modified_files
