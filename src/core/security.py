"""
Security scanner for AI-generated code.

Scans every code change for vulnerabilities using:
1. Custom regex patterns (instant, catches common issues)
2. Semgrep rules (OWASP Top 10 + language-specific, ~2-5 seconds)
3. Language-specific scanners (Bandit for Python, etc.)

Security badge system:
- 🟢 CLEAN:   No security issues detected
- 🟡 WARNING: Potential issues (details shown, user decides)
- 🔴 BLOCKED: Critical vulnerability, agent asked to auto-fix before presenting

Auto-fix flow for BLOCKED patches:
1. Critical issue found → send finding back to agent with targeted fix request
2. Agent generates fixed version → re-scan
3. If clean → present with "Security issue auto-fixed" note
4. If still blocked after 2 attempts → present with RED warning, user acknowledges
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from src.core.diff_engine import PatchSet
from src.core.logger import get_logger

logger = get_logger("core.security")


@dataclass
class SecurityFinding:
    """One security issue found in AI-generated code."""

    file_path: str
    line_number: int
    rule_id: str  # e.g. "custom.sql-injection", "semgrep.python.injection"
    severity: str  # "critical", "high", "medium", "low", "info"
    message: str
    category: str  # "injection", "xss", "secrets", "auth", "crypto", etc.
    cwe_id: str | None = None  # CWE reference for standards compliance
    fix_suggestion: str | None = None
    source: str = "custom"  # "custom", "semgrep", "bandit"


# =============================================================================
# Custom regex patterns for fast, always-available scanning
# These run instantly on every patch, no external tools needed
# =============================================================================

SECURITY_PATTERNS: list[tuple[str, str, str, str, str | None]] = [
    # (regex, message, severity, category, cwe_id)
    # SQL Injection
    (
        r'f["\'].*?(?:SELECT|INSERT|UPDATE|DELETE|DROP)\b.*?\{',
        "Possible SQL injection via f-string interpolation",
        "critical",
        "injection",
        "CWE-89",
    ),
    (
        r"\.format\s*\(.*?\).*?(?:SELECT|INSERT|UPDATE|DELETE)",
        "Possible SQL injection via .format()",
        "critical",
        "injection",
        "CWE-89",
    ),
    (
        r'(?:execute|executemany|raw)\s*\(\s*["\']?\s*\+',
        "Possible SQL injection via string concatenation",
        "critical",
        "injection",
        "CWE-89",
    ),
    (
        r'cursor\s*\.\s*execute\s*\(\s*f["\']',
        "SQL injection: f-string in cursor.execute()",
        "critical",
        "injection",
        "CWE-89",
    ),
    # Hardcoded Secrets
    (
        r'(?:password|passwd|pwd|secret|api_key|apikey|access_token|auth_token)\s*=\s*["\'][^"\']{8,}["\']',
        "Possible hardcoded secret or credential",
        "high",
        "secrets",
        "CWE-798",
    ),
    (
        r'(?:AWS_SECRET|AWS_ACCESS|AZURE_KEY|GCP_KEY|GITHUB_TOKEN)\s*=\s*["\']',
        "Possible hardcoded cloud credential",
        "high",
        "secrets",
        "CWE-798",
    ),
    (
        r"(?:Bearer|Basic)\s+[A-Za-z0-9+/=]{20,}",
        "Possible hardcoded authentication token",
        "high",
        "secrets",
        "CWE-798",
    ),
    # XSS
    (
        r'innerHTML\s*=(?!\s*["\']$)',
        "Possible XSS via innerHTML assignment",
        "high",
        "xss",
        "CWE-79",
    ),
    (
        r"dangerouslySetInnerHTML",
        "React dangerouslySetInnerHTML — potential XSS",
        "medium",
        "xss",
        "CWE-79",
    ),
    (r"document\.write\s*\(", "Possible XSS via document.write()", "high", "xss", "CWE-79"),
    (
        r"\.html\s*\(\s*[^)]*\+",
        "Possible XSS via jQuery .html() with concatenation",
        "medium",
        "xss",
        "CWE-79",
    ),
    # Command Injection
    (
        r'(?:os\.system|os\.popen|subprocess\.call)\s*\(\s*(?:f["\']|["\'].*?\+|.*?\.format)',
        "Possible command injection via user input in system call",
        "critical",
        "injection",
        "CWE-78",
    ),
    (
        r"subprocess\.\w+\([^)]*shell\s*=\s*True",
        "Shell=True in subprocess — possible command injection",
        "high",
        "injection",
        "CWE-78",
    ),
    (
        r'eval\s*\(\s*(?![\'"]\s*\))',
        "Use of eval() — potential code injection",
        "high",
        "injection",
        "CWE-95",
    ),
    (
        r'exec\s*\(\s*(?![\'"]\s*\))',
        "Use of exec() — potential code injection",
        "high",
        "injection",
        "CWE-95",
    ),
    # Path Traversal
    (
        r"open\s*\(\s*(?:request|user|input|params|args)",
        "Possible path traversal from user input",
        "medium",
        "path_traversal",
        "CWE-22",
    ),
    (
        r"os\.path\.join\s*\([^)]*(?:request|user|input|params)",
        "Possible path traversal in os.path.join with user input",
        "medium",
        "path_traversal",
        "CWE-22",
    ),
    # Weak Cryptography
    (
        r"(?:hashlib\.)?(?:md5|sha1)\s*\(",
        "Weak hash algorithm — use SHA-256 or stronger",
        "medium",
        "crypto",
        "CWE-328",
    ),
    (
        r"(?:^|\W)random\.\w+\(\)",
        "Non-cryptographic random — use secrets module for security",
        "low",
        "crypto",
        "CWE-330",
    ),
    (
        r"DES\b|Blowfish\b|RC4\b",
        "Weak or deprecated encryption algorithm",
        "medium",
        "crypto",
        "CWE-327",
    ),
    # Authentication / Session
    (r"verify\s*=\s*False", "SSL/TLS verification disabled", "high", "auth", "CWE-295"),
    (
        r'CORS\s*\(\s*\*\s*\)|allow_origins\s*=\s*\[\s*["\']\*["\']\s*\]',
        "CORS wildcard — allows any origin",
        "medium",
        "auth",
        "CWE-942",
    ),
    # Deserialization
    (
        r"pickle\.loads?\s*\(",
        "Unsafe deserialization via pickle",
        "high",
        "deserialization",
        "CWE-502",
    ),
    (
        r"yaml\.load\s*\(\s*[^)]*(?!Loader\s*=\s*yaml\.SafeLoader)",
        "Unsafe YAML loading — use yaml.safe_load()",
        "medium",
        "deserialization",
        "CWE-502",
    ),
]


class SecurityScanner:
    """
    Scans PatchSets for security vulnerabilities.

    Three layers:
    1. Custom patterns (instant, regex-based, always available)
    2. Semgrep (if installed, OWASP + language rules)
    3. Language-specific (Bandit for Python)

    The scanner only checks MODIFIED lines — not the entire file.
    This prevents false positives from pre-existing issues.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = project_root
        self._custom_block_patterns: list[str] = []
        self._custom_allow_patterns: list[str] = []
        self._warned_missing: set[str] = set()
        self._load_project_rules()

    def _load_project_rules(self) -> None:
        """Load project-specific security rules from .gptcgt/security-rules.toml."""
        if not self._project_root:
            return
        rules_path = self._project_root / ".gptcgt" / "security-rules.toml"
        if not rules_path.exists():
            return
        try:
            import tomllib

            with open(rules_path, "rb") as f:
                rules = tomllib.load(f)
            self._custom_block_patterns = rules.get("rules", {}).get("block_patterns", [])
            self._custom_allow_patterns = rules.get("rules", {}).get("allow_patterns", [])
            logger.info(
                f"Loaded {len(self._custom_block_patterns)} custom block patterns, "
                f"{len(self._custom_allow_patterns)} allow patterns"
            )
        except Exception as e:
            logger.warning(f"Failed to load security rules: {e}")

    async def scan_patch(self, patch_set: PatchSet, language: str) -> list[SecurityFinding]:
        """
        Scan a PatchSet for security issues.
        Only scans MODIFIED lines to avoid false positives from existing code.

        Returns list of findings sorted by severity (critical first).
        """
        findings: list[SecurityFinding] = []

        # Layer 1: Custom regex patterns (instant, always available)
        findings.extend(self._scan_custom_patterns(patch_set))

        # Layer 2: Project-specific block patterns
        findings.extend(self._scan_project_patterns(patch_set))

        # Layer 3: Semgrep (if installed)
        if shutil.which("semgrep"):
            semgrep_findings = await self._run_semgrep(patch_set, language)
            findings.extend(semgrep_findings)
        else:
            self._notify_missing_scanner("Semgrep")

        # Layer 4: Language-specific (Bandit for Python)
        if language == "python":
            if shutil.which("bandit"):
                bandit_findings = await self._run_bandit(patch_set)
                findings.extend(bandit_findings)
            else:
                self._notify_missing_scanner("Bandit")

        # Filter out allowed patterns
        findings = self._filter_allowed(findings)

        # Sort: critical first, then high, medium, low
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        findings.sort(key=lambda f: severity_order.get(f.severity, 5))

        return findings

    def _notify_missing_scanner(self, name: str) -> None:
        if name in self._warned_missing:
            return
        self._warned_missing.add(name)
        try:
            from src.tui.widgets.toast import notify  # noqa: I001
            import textual.app as _tapp
            app = _tapp.active_app.get()
            app.call_from_thread(
                notify,
                title="Security Alert",
                message=f"Running in reduced scan mode: '{name}' not installed.",
                severity="warning",
                timeout=8.0
            )
        except Exception as e:
            logger.debug(f"Could not push missing scanner toast: {e}")

    def _scan_custom_patterns(self, patch_set: PatchSet) -> list[SecurityFinding]:
        """Scan modified lines against built-in regex patterns."""
        findings: list[SecurityFinding] = []

        for fp in patch_set.patches:
            for hunk in fp.hunks:
                for i, line in enumerate(hunk.modified_lines):
                    line_stripped = line.strip()
                    if (
                        not line_stripped
                        or line_stripped.startswith("#")
                        or line_stripped.startswith("//")
                    ):
                        continue  # Skip comments and blank lines

                    for pattern, message, severity, category, cwe_id in SECURITY_PATTERNS:
                        if re.search(pattern, line_stripped, re.IGNORECASE):
                            findings.append(
                                SecurityFinding(
                                    file_path=str(fp.file_path),
                                    line_number=hunk.start_line + i,
                                    rule_id=f"custom.{category}",
                                    severity=severity,
                                    message=message,
                                    category=category,
                                    cwe_id=cwe_id,
                                    source="custom",
                                )
                            )

        return findings

    def _scan_project_patterns(self, patch_set: PatchSet) -> list[SecurityFinding]:
        """Scan against project-specific block patterns from .gptcgt/security-rules.toml."""
        findings: list[SecurityFinding] = []

        for fp in patch_set.patches:
            for hunk in fp.hunks:
                for i, line in enumerate(hunk.modified_lines):
                    for pattern in self._custom_block_patterns:
                        if pattern in line:
                            findings.append(
                                SecurityFinding(
                                    file_path=str(fp.file_path),
                                    line_number=hunk.start_line + i,
                                    rule_id="project.block-pattern",
                                    severity="high",
                                    message=f"Blocked by project rule: '{pattern}'",
                                    category="project-policy",
                                    source="project-rules",
                                )
                            )

        return findings

    async def _run_semgrep(self, patch_set: PatchSet, language: str) -> list[SecurityFinding]:
        """Run semgrep on modified files. Returns findings for modified lines only."""
        findings: list[SecurityFinding] = []

        if not self._project_root:
            return findings

        # Collect modified file paths
        modified_files = [
            str(self._project_root / fp.file_path)
            for fp in patch_set.patches
            if (self._project_root / fp.file_path).exists()
        ]
        if not modified_files:
            return findings

        # Get modified line numbers per file for filtering
        modified_lines_map: dict[str, set[int]] = {}
        for fp in patch_set.patches:
            line_nums: set[int] = set()
            for hunk in fp.hunks:
                for i in range(len(hunk.modified_lines)):
                    line_nums.add(hunk.start_line + i)
            modified_lines_map[str(fp.file_path)] = line_nums

        try:
            proc = await asyncio.create_subprocess_exec(
                "semgrep",
                "--config",
                "auto",
                "--json",
                "--quiet",
                *modified_files,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

            data = json.loads(stdout.decode()) if stdout else {}
            results = data.get("results", [])

            for r in results:
                file_path = r.get("path", "")
                line = r.get("start", {}).get("line", 0)

                # Only include findings on MODIFIED lines
                rel_path = str(Path(file_path).relative_to(self._project_root))
                if rel_path in modified_lines_map and line in modified_lines_map[rel_path]:
                    severity_map = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}
                    findings.append(
                        SecurityFinding(
                            file_path=rel_path,
                            line_number=line,
                            rule_id=r.get("check_id", "semgrep.unknown"),
                            severity=severity_map.get(r.get("severity", ""), "medium"),
                            message=r.get("extra", {}).get("message", "Semgrep finding"),
                            category=self._categorize_semgrep_rule(r.get("check_id", "")),
                            cwe_id=r.get("extra", {}).get("metadata", {}).get("cwe", [None])[0]
                            if isinstance(r.get("extra", {}).get("metadata", {}).get("cwe"), list)
                            else None,
                            source="semgrep",
                        )
                    )
        except asyncio.TimeoutError:
            logger.warning("Semgrep timed out after 60 seconds")
        except Exception as e:
            logger.warning(f"Semgrep failed: {e}")

        return findings

    async def _run_bandit(self, patch_set: PatchSet) -> list[SecurityFinding]:
        """Run Bandit (Python security linter) on modified files."""
        findings: list[SecurityFinding] = []

        if not self._project_root:
            return findings

        python_files = [
            str(self._project_root / fp.file_path)
            for fp in patch_set.patches
            if str(fp.file_path).endswith(".py") and (self._project_root / fp.file_path).exists()
        ]
        if not python_files:
            return findings

        try:
            proc = await asyncio.create_subprocess_exec(
                "bandit",
                "-f",
                "json",
                "-q",
                *python_files,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            data = json.loads(stdout.decode()) if stdout else {}

            for r in data.get("results", []):
                severity_map = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
                findings.append(
                    SecurityFinding(
                        file_path=str(Path(r.get("filename", "")).relative_to(self._project_root)),
                        line_number=r.get("line_number", 0),
                        rule_id=r.get("test_id", "bandit.unknown"),
                        severity=severity_map.get(r.get("issue_severity", ""), "medium"),
                        message=r.get("issue_text", "Bandit finding"),
                        category=r.get("issue_cwe", {}).get("link", "general"),
                        cwe_id=f"CWE-{r.get('issue_cwe', {}).get('id', '')}"
                        if r.get("issue_cwe")
                        else None,
                        source="bandit",
                    )
                )
        except Exception as e:
            logger.warning(f"Bandit failed: {e}")

        return findings

    def _filter_allowed(self, findings: list[SecurityFinding]) -> list[SecurityFinding]:
        """Remove findings that match project allow patterns."""
        if not self._custom_allow_patterns:
            return findings
        return [
            f
            for f in findings
            if not any(pattern in f.message for pattern in self._custom_allow_patterns)
        ]

    def _categorize_semgrep_rule(self, rule_id: str) -> str:
        """Map semgrep rule IDs to categories."""
        if "injection" in rule_id or "sqli" in rule_id:
            return "injection"
        if "xss" in rule_id:
            return "xss"
        if "crypto" in rule_id:
            return "crypto"
        if "auth" in rule_id or "session" in rule_id:
            return "auth"
        if "deserialization" in rule_id:
            return "deserialization"
        return "general"

    def get_badge(self, findings: list[SecurityFinding]) -> str:
        """Determine the security badge from findings."""
        if any(f.severity == "critical" for f in findings):
            return "blocked"
        if any(f.severity in ("high", "medium") for f in findings):
            return "warning"
        return "clean"

    def format_findings(self, findings: list[SecurityFinding]) -> str:
        """Format findings for display in narration."""
        if not findings:
            return "🟢 No security issues detected"

        badge = self.get_badge(findings)
        lines = []

        if badge == "blocked":
            lines.append("🔴 CRITICAL security issues found:")
        elif badge == "warning":
            lines.append("🟡 Security warnings:")

        for f in findings[:5]:  # Show max 5
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(
                f.severity, "⚪"
            )
            lines.append(
                f"  {emoji} [{f.severity.upper()}] {f.file_path}:{f.line_number} — {f.message}"
            )
            if f.cwe_id:
                lines.append(f"    ({f.cwe_id})")

        if len(findings) > 5:
            lines.append(f"  ... and {len(findings) - 5} more findings")

        return "\n".join(lines)
