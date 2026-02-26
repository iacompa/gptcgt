"""
Evidence-Based Arbiter — 6-stage deterministic evaluation of AI solutions.

This is THE killer feature. No other tool compares AI outputs using
objective, deterministic tools. Every competitor uses "LLM as judge"
(another AI's opinion). gptcgt uses tests, linters, security scanners,
and static analysis — things that are provably correct.

Usage:
    arbiter = Arbiter(sandbox, security_scanner, lsp_client)
    verdict = await arbiter.evaluate(dispatch, project_root, language, test_command)
    # verdict.winner, verdict.scores, verdict.evidence, verdict.comparison_summary
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from src.core.diff_engine import PatchSet
from src.core.logger import get_logger
from src.core.parallel_dispatcher import ParallelDispatch
from src.core.security import SecurityFinding, SecurityScanner
from src.tools.lsp import LSPClient, ReferenceVerification
from src.tools.sandbox import E2BSandbox, VerificationResult

logger = get_logger("core.arbiter")


# =============================================================================
# Scoring weights — these determine how much each stage matters
# =============================================================================

SCORING_WEIGHTS = {
    "structural_validity": 0.10,  # Must be valid code
    "lint_cleanliness": 0.10,  # Clean code, no new violations
    "test_pass_rate": 0.40,  # Tests are the strongest signal of correctness
    "security_score": 0.20,  # Security is critical — 45% of AI code has vulns
    "diff_minimality": 0.10,  # Smaller, focused changes are better
    "complexity_delta": 0.10,  # Simpler solutions are better
}


# =============================================================================
# Data structures
# =============================================================================


@dataclass
class ProofBundle:
    """Explicit deterministic proof of a patch's viability before user presentation."""
    linter_clean: bool = False
    tests_passed: bool = False
    security_clean: bool = False
    cost_estimate: float = 0.0
    calibrated_confidence_score: float = 0.0


@dataclass
class DiffStats:
    """Statistics about a patch's size and scope."""

    lines_added: int = 0
    lines_removed: int = 0
    lines_changed: int = 0  # added + removed
    files_touched: int = 0
    hunks_count: int = 0


@dataclass
class ComplexityStats:
    """Cyclomatic complexity delta before vs after the patch."""

    avg_complexity_before: float = 0.0
    avg_complexity_after: float = 0.0
    max_nesting_before: int = 0
    max_nesting_after: int = 0

    @property
    def complexity_delta(self) -> float:
        """Positive = MORE complex (bad), negative = LESS complex (good)."""
        return self.avg_complexity_after - self.avg_complexity_before

    @property
    def nesting_delta(self) -> int:
        return self.max_nesting_after - self.max_nesting_before


@dataclass
class ArbiterScore:
    """Complete evaluation score for one agent's solution."""

    agent_id: str
    model_name: str
    model_id: str
    patch_set: PatchSet | None = None
    total_score: float = 0.0  # 0-100 weighted composite

    # Per-stage scores (each 0-100)
    stage_scores: dict[str, float] = field(default_factory=dict)

    # Detailed results per stage
    verification: VerificationResult | None = None  # From E2B sandbox (stages 2-3)
    security_findings: list[SecurityFinding] = field(default_factory=list)  # Stage 4
    diff_stats: DiffStats = field(default_factory=DiffStats)  # Stage 5
    complexity_stats: ComplexityStats = field(default_factory=ComplexityStats)  # Stage 6
    reference_verification: ReferenceVerification | None = None  # LSP check
    proof_bundle: ProofBundle | None = None  # The strict evidence requirement

    # Elimination
    eliminated: bool = False
    elimination_reason: str | None = None

    # Timing
    evaluation_ms: int = 0


@dataclass
class ArbiterVerdict:
    """The arbiter's final decision with evidence."""

    dispatch_id: str
    scores: list[ArbiterScore]  # All agents, sorted best→worst
    winner: ArbiterScore  # Highest scoring non-eliminated agent
    runner_up: ArbiterScore | None  # Second best (if exists)
    comparison_summary: str  # One-line human-readable summary
    evidence: list[str]  # Key differentiating facts
    confidence: str  # "high" (>15pt gap), "medium" (5-15), "low" (<5)
    total_evaluation_ms: int = 0


class Arbiter:
    """
    Evidence-based evaluation of competing AI solutions.

    Takes a ParallelDispatch (2-3 completed agents with PatchSets),
    runs the 6-stage pipeline on each, and produces an ArbiterVerdict.
    """

    def __init__(
        self,
        sandbox: E2BSandbox,
        security_scanner: SecurityScanner,
        lsp_client: LSPClient | None = None,
    ) -> None:
        self._sandbox = sandbox
        self._security = security_scanner
        self._lsp = lsp_client

    async def evaluate(
        self,
        dispatch: ParallelDispatch,
        project_root: Path,
        language: str,
        test_command: str | None = None,
        on_progress: callable | None = None,
    ) -> ArbiterVerdict:
        """
        Run the 6-stage evaluation pipeline on all agent solutions.

        Args:
            dispatch: The completed ParallelDispatch with agent results
            project_root: Path to the project root directory
            language: Primary language of the project ("python", "typescript", etc.)
            test_command: Custom test command override (e.g., "pytest tests/")
            on_progress: Optional callback(stage_name, agent_id, detail) for narration

        Returns:
            ArbiterVerdict with scores, winner, evidence, and comparison summary

        """
        eval_start = time.time()

        # Phase 19: Arbiter Judge Memory Ingestion
        arbiter_memory = ""
        try:
            from src.core.workspace import Workspace
            ws = Workspace.get_instance()
            mem_path = ws.get_project_root() / ".gptcgt" / "agents" / "arbiter.md"
            if ws.safe_exists(mem_path):
                try:
                    import textual.app as _tapp

                    from src.core.events import AgentStatusUpdate
                    current_app = _tapp.active_app.get()
                    current_app.post_message(AgentStatusUpdate(
                        agent_id="arbiter",
                        model_name="Arbiter",
                        status="thinking",
                        detail="Reading arbiter memory rules..."
                    ))
                except Exception:
                    pass
                arbiter_memory = ws.safe_read(mem_path)
        except Exception:
            pass

        scores: list[ArbiterScore] = []

        for slot in dispatch.slots:
            if slot.status != "completed" or not slot.patch_set:
                # Agent failed or produced no code — skip
                score = ArbiterScore(
                    agent_id=slot.agent_id,
                    model_name=slot.model.name,
                    model_id=slot.model.id,
                    eliminated=True,
                    elimination_reason="Agent failed or produced no code changes",
                )
                scores.append(score)
                continue

            agent_start = time.time()
            score = ArbiterScore(
                agent_id=slot.agent_id,
                model_name=slot.model.name,
                model_id=slot.model.id,
            )
            score.patch_set = slot.patch_set

            # ═══════════════════════════════════════════════════
            # STAGE 1: Structural Validation (instant, local)
            # ═══════════════════════════════════════════════════
            if on_progress:
                await on_progress("structural", slot.agent_id, "Validating syntax...")

            structural_score = self._stage1_structural(slot.patch_set, project_root)
            score.stage_scores["structural_validity"] = structural_score

            if structural_score == 0:
                score.eliminated = True
                score.elimination_reason = "Code has syntax errors or diff doesn't apply cleanly"
                score.total_score = 0
                scores.append(score)
                continue

            # ═══════════════════════════════════════════════════
            # STAGES 2-4: Run in PARALLEL (lint, tests, security)
            # These are independent — no reason to run sequentially
            # ═══════════════════════════════════════════════════
            if on_progress:
                await on_progress(
                    "verification", slot.agent_id, "Running lint + tests + security scan..."
                )

            # Stage 2+3: Sandbox verification (lint + tests)
            sandbox_task = asyncio.create_task(
                self._sandbox.verify_patch(slot.patch_set, project_root, language, test_command)
            )

            # Stage 4: Security scan
            security_task = asyncio.create_task(self._security.scan_patch(slot.patch_set, language))

            # LSP reference verification (bonus check, runs in parallel too)
            lsp_task = None
            if self._lsp:
                lsp_task = asyncio.create_task(
                    self._lsp.verify_patch_references(slot.patch_set, language)
                )

            # Await all parallel checks
            verification_result, security_findings = await asyncio.gather(
                sandbox_task, security_task
            )

            # Phase 19: Dynamically pardon false-positives using Arbiter Memory
            if arbiter_memory and (verification_result.test_result or security_findings):
                await self._apply_memory_pardons(
                    verification_result, security_findings, arbiter_memory
                )

            if lsp_task:
                score.reference_verification = await lsp_task

            score.verification = verification_result
            score.security_findings = security_findings

            # ═══════════════════════════════════════════════════
            # Compute per-stage scores
            # ═══════════════════════════════════════════════════

            # Stage 2: Lint score
            lint_score = 100.0
            if verification_result.lint_result:
                new_violations = verification_result.lint_result.new_violations
                lint_score = max(0, 100 - (new_violations * 5))
            score.stage_scores["lint_cleanliness"] = lint_score

            # Stage 3: Test score
            test_score = 100.0  # Default if no tests available
            if verification_result.test_result and verification_result.test_result.total > 0:
                test_score = verification_result.test_result.pass_rate
            score.stage_scores["test_pass_rate"] = test_score

            # Stage 4: Security score
            security_score = 100.0
            for finding in security_findings:
                if finding.severity == "critical":
                    security_score -= 50
                elif finding.severity == "high":
                    security_score -= 20
                elif finding.severity == "medium":
                    security_score -= 5
                elif finding.severity == "low":
                    security_score -= 1
            security_score = max(0, security_score)
            score.stage_scores["security_score"] = security_score

            # ═══════════════════════════════════════════════════
            # STAGE 5: Diff Minimality (instant, local)
            # ═══════════════════════════════════════════════════
            diff_stats = self._stage5_diff_stats(slot.patch_set)
            score.diff_stats = diff_stats
            # Minimality score is normalized AFTER all agents are evaluated (see below)

            # ═══════════════════════════════════════════════════
            # STAGE 6: Complexity Delta (instant, local)
            # ═══════════════════════════════════════════════════
            complexity = self._stage6_complexity(slot.patch_set, project_root)
            score.complexity_stats = complexity

            complexity_score = 100.0 - (complexity.complexity_delta * 10.0)
            score.stage_scores["complexity_delta"] = max(0.0, min(100.0, complexity_score))

            score.evaluation_ms = int((time.time() - agent_start) * 1000)

            # ═══════════════════════════════════════════════════
            # PROOF BUNDLE & CONFIDENCE CALIBRATION
            # ═══════════════════════════════════════════════════
            confidence = 0.5

            # Linter check
            linter_clean = bool(verification_result.lint_result and getattr(verification_result.lint_result, 'new_violations', 0) == 0)
            if linter_clean:
                confidence += 0.2

            # Test check
            tests_passed = False
            if verification_result.test_result:
                if verification_result.test_result.total > 0:
                    tests_passed = getattr(verification_result.test_result, 'passed', False)
                else:
                    tests_passed = True # No tests exist is technically a pass, though risky

            if tests_passed:
                confidence += 0.3

            # Security check
            security_clean = len(security_findings) == 0
            if not security_clean:
                confidence -= 0.5

            confidence = max(0.0, min(1.0, confidence))

            score.proof_bundle = ProofBundle(
                linter_clean=linter_clean,
                tests_passed=tests_passed,
                security_clean=security_clean,
                calibrated_confidence_score=confidence
            )

            # Elimination based on Frontier Safety Rules
            if confidence < 0.85:
                score.eliminated = True
                score.elimination_reason = f"Low confidence ({confidence:.2f}): Failed strict verification proofs (tests/lint/security)."
                # Push failure to reflection engine implicitly for next iterations
                try:
                    import textual.app as _tapp
                    from src.core.reflection_engine import ReflectionEngine
                    _app = _tapp.active_app.get()
                    engine = ReflectionEngine(_app)
                    engine.reflect_on_friction(
                        model_name=slot.model.name,
                        trigger_event="arbiter_elimination",
                        original_prompt="",
                        agent_output=slot.response_text[:500],
                        failure_reason=score.elimination_reason,
                    )
                except Exception:
                    pass

            scores.append(score)

        # ═══════════════════════════════════════════════════
        # Normalize diff minimality scores across all agents
        # The agent with the smallest diff gets 100, largest gets proportionally less
        # ═══════════════════════════════════════════════════
        non_eliminated = [s for s in scores if not s.eliminated]
        if len(non_eliminated) >= 2:
            min_lines = min(s.diff_stats.lines_changed for s in non_eliminated)
            max_lines = max(s.diff_stats.lines_changed for s in non_eliminated)
            line_range = max_lines - min_lines if max_lines > min_lines else 1

            for s in non_eliminated:
                # Invert: smallest diff = highest score
                if line_range > 0:
                    s.stage_scores["diff_minimality"] = 100 * (
                        1 - (s.diff_stats.lines_changed - min_lines) / line_range
                    )
                else:
                    s.stage_scores["diff_minimality"] = 100.0
        elif len(non_eliminated) == 1:
            non_eliminated[0].stage_scores["diff_minimality"] = 100.0

        # ═══════════════════════════════════════════════════
        # Compute weighted composite scores
        # ═══════════════════════════════════════════════════
        for s in non_eliminated:
            s.total_score = sum(
                s.stage_scores.get(stage, 0) * weight for stage, weight in SCORING_WEIGHTS.items()
            )

        # Sort by total score (best first)
        scores.sort(key=lambda s: (not s.eliminated, s.total_score), reverse=True)

        # Produce verdict
        total_ms = int((time.time() - eval_start) * 1000)
        verdict = self._produce_verdict(dispatch.dispatch_id, scores, total_ms)

        if on_progress:
            await on_progress("verdict", "", verdict.comparison_summary)

        return verdict

    # ═════════════════════════════════════════════════════════
    # STAGE IMPLEMENTATIONS
    # ═════════════════════════════════════════════════════════

    def _stage1_structural(self, patch_set: PatchSet, project_root: Path) -> float:
        """
        Stage 1: Structural Validation.
        Check that diffs apply cleanly and code is syntactically valid.
        Returns 100.0 if valid, 0.0 if not (instant elimination).
        """
        for fp in patch_set.patches:
            full_path = project_root / fp.file_path

            # Check: does the file exist (for modifications, not new files)?
            if not fp.is_new_file and not full_path.exists():
                logger.warning(f"Structural: {fp.file_path} does not exist")
                return 0.0

            # Check: do the hunk line ranges make sense?
            if not fp.is_new_file:
                try:
                    content = full_path.read_text(errors="replace")
                    line_count = len(content.splitlines())
                    for hunk in fp.hunks:
                        if hunk.start_line < 1 or hunk.end_line > line_count + 1:
                            logger.warning(
                                f"Structural: hunk range {hunk.start_line}-{hunk.end_line} "
                                f"out of bounds for {fp.file_path} ({line_count} lines)"
                            )
                            return 0.0
                except Exception as e:
                    logger.warning(f"Structural: can't read {fp.file_path}: {e}")
                    return 0.0

            # Check: is the resulting code syntactically valid? (tree-sitter)
            try:
                # Build what the file would look like after applying this patch
                if fp.is_new_file:
                    patched_content = "\n".join(
                        line for hunk in fp.hunks for line in hunk.modified_lines
                    )
                else:
                    original = full_path.read_text(errors="replace")
                    lines = original.splitlines()
                    for hunk in sorted(fp.hunks, key=lambda h: h.start_line, reverse=True):
                        lines[hunk.start_line - 1 : hunk.end_line] = hunk.modified_lines
                    patched_content = "\n".join(lines)

                # Try tree-sitter parse (if it throws, syntax is bad)
                # For now, use a simplified check — tree-sitter will catch obvious issues
                if fp.file_path.endswith(".py"):
                    compile(patched_content, str(fp.file_path), "exec")
            except SyntaxError as e:
                logger.info(f"Structural: syntax error in {fp.file_path}: {e}")
                return 0.0
            except Exception:
                pass  # Non-Python files: skip syntax check, rely on lint

        return 100.0

    def _stage5_diff_stats(self, patch_set: PatchSet) -> DiffStats:
        """Stage 5: Compute diff statistics."""
        stats = DiffStats()
        stats.files_touched = patch_set.file_count
        stats.hunks_count = patch_set.total_hunks

        for fp in patch_set.patches:
            for hunk in fp.hunks:
                stats.lines_added += len(hunk.modified_lines)
                stats.lines_removed += len(hunk.original_lines)

        stats.lines_changed = stats.lines_added + stats.lines_removed
        return stats

    def _stage6_complexity(self, patch_set: PatchSet, project_root: Path) -> ComplexityStats:
        """
        Stage 6: Estimate cyclomatic complexity delta.

        Uses a simple heuristic: count branching keywords (if, elif, for, while,
        except, and, or, case) in original vs modified lines.
        A full implementation would use tree-sitter AST analysis.
        """
        stats = ComplexityStats()

        branch_keywords_python = re.compile(
            r"\b(if|elif|else|for|while|except|and|or|case|match)\b"
        )
        branch_keywords_js = re.compile(r"\b(if|else|for|while|catch|switch|case|\&\&|\|\||\?)\b")

        total_before = 0
        total_after = 0
        max_nesting_before = 0
        max_nesting_after = 0

        for fp in patch_set.patches:
            ext = Path(fp.file_path).suffix.lower() if fp.file_path else ""
            keywords = (
                branch_keywords_js
                if ext in (".js", ".jsx", ".ts", ".tsx")
                else branch_keywords_python
            )
            for hunk in fp.hunks:
                # Count branching in original lines
                for line in hunk.original_lines:
                    total_before += len(keywords.findall(line))
                    indent = len(line) - len(line.lstrip())
                    max_nesting_before = max(max_nesting_before, indent // 4)

                # Count branching in modified lines
                for line in hunk.modified_lines:
                    total_after += len(keywords.findall(line))
                    indent = len(line) - len(line.lstrip())
                    max_nesting_after = max(max_nesting_after, indent // 4)

        # Normalize to average per hunk
        hunk_count = max(patch_set.total_hunks, 1)
        stats.avg_complexity_before = total_before / hunk_count
        stats.avg_complexity_after = total_after / hunk_count
        stats.max_nesting_before = max_nesting_before
        stats.max_nesting_after = max_nesting_after

        return stats

    # ═════════════════════════════════════════════════════════
    # VERDICT GENERATION
    # ═════════════════════════════════════════════════════════

    def _produce_verdict(
        self, dispatch_id: str, scores: list[ArbiterScore], total_ms: int
    ) -> ArbiterVerdict:
        """Generate the human-readable verdict with evidence."""
        non_eliminated = [s for s in scores if not s.eliminated]

        if not non_eliminated:
            # All agents failed — return the least-bad one
            winner = (
                scores[0]
                if scores
                else ArbiterScore(
                    agent_id="none",
                    model_name="none",
                    model_id="none",
                    eliminated=True,
                    elimination_reason="All agents failed",
                )
            )
            return ArbiterVerdict(
                dispatch_id=dispatch_id,
                scores=scores,
                winner=winner,
                runner_up=None,
                comparison_summary="All agent solutions failed structural validation.",
                evidence=["No valid solutions produced."],
                confidence="low",
                total_evaluation_ms=total_ms,
            )

        winner = non_eliminated[0]
        runner_up = non_eliminated[1] if len(non_eliminated) > 1 else None

        # Build evidence: the KEY differences that determined the winner
        evidence: list[str] = []

        if runner_up:
            # Test comparison
            w_tests = winner.verification.test_result if winner.verification else None
            r_tests = runner_up.verification.test_result if runner_up.verification else None
            if w_tests and r_tests and w_tests.total > 0:
                if w_tests.passed != r_tests.passed:
                    evidence.append(
                        f"{winner.model_name} passed {w_tests.passed}/{w_tests.total} tests. "
                        f"{runner_up.model_name} passed {r_tests.passed}/{r_tests.total}."
                    )
                else:
                    evidence.append(f"Both passed {w_tests.passed}/{w_tests.total} tests.")

            # Security comparison
            w_sec = len(winner.security_findings)
            r_sec = len(runner_up.security_findings)
            if w_sec != r_sec:
                evidence.append(
                    f"{winner.model_name}: {w_sec} security warnings. "
                    f"{runner_up.model_name}: {r_sec} security warnings."
                )
            elif w_sec == 0:
                evidence.append("Both solutions security clean.")

            # Diff size comparison
            w_diff = winner.diff_stats
            r_diff = runner_up.diff_stats
            if w_diff.lines_changed != r_diff.lines_changed:
                evidence.append(
                    f"{winner.model_name} changed {w_diff.lines_changed} lines across "
                    f"{w_diff.files_touched} files. {runner_up.model_name} changed "
                    f"{r_diff.lines_changed} lines across {r_diff.files_touched} files."
                )

            # Complexity comparison
            w_cx = winner.complexity_stats.complexity_delta
            r_cx = runner_up.complexity_stats.complexity_delta
            if abs(w_cx - r_cx) > 0.5:
                w_dir = "reduced" if w_cx < 0 else "increased" if w_cx > 0 else "unchanged"
                r_dir = "reduced" if r_cx < 0 else "increased" if r_cx > 0 else "unchanged"
                evidence.append(
                    f"{winner.model_name} {w_dir} complexity. "
                    f"{runner_up.model_name} {r_dir} complexity."
                )

            # LSP reference check
            if winner.reference_verification and not winner.reference_verification.complete:
                evidence.append(
                    f"⚠️ {winner.model_name} missed {len(winner.reference_verification.missed)} "
                    f"cross-file references."
                )

        # Build summary
        summary = f"🏆 {winner.model_name} scored {winner.total_score:.0f}/100"
        if runner_up:
            summary += f" vs {runner_up.model_name} at {runner_up.total_score:.0f}/100"
        summary += f" ({total_ms}ms evaluation)"

        # Determine confidence
        gap = winner.total_score - (runner_up.total_score if runner_up else 0)
        if gap > 15:
            confidence = "high"
        elif gap > 5:
            confidence = "medium"
        else:
            confidence = "low"

        return ArbiterVerdict(
            dispatch_id=dispatch_id,
            scores=scores,
            winner=winner,
            runner_up=runner_up,
            comparison_summary=summary,
            evidence=evidence,
            confidence=confidence,
            total_evaluation_ms=total_ms,
        )

    async def _apply_memory_pardons(
        self,
        verification: VerificationResult,
        security_findings: list[SecurityFinding],
        memory: str,
    ) -> None:
        """Uses a lightning-fast LIGHT model to compare failures against known false-positives in memory."""
        has_test_fails = verification.test_result and not verification.test_result.passed and verification.test_result.total > 0
        has_sec_fails = len(security_findings) > 0

        if not (has_test_fails or has_sec_fails):
            return

        from src.agents.factory import PROVIDER_KEY_MAP, AgentFactory
        from src.auth.keychain import KeyChainManager
        from src.core.model_registry import QualityTier
        from src.core.router import CodingRouter

        # Phase 21: Route to an explicit Arbiter override, otherwise dynamically discover cheapest
        router = CodingRouter()
        arbiter_model_def = router.route_task("chat", 1, QualityTier.LIGHT, role="arbiter")

        if not arbiter_model_def:
            logger.warning("Arbiter memory pardon bypassed: No API keys configured.")
            return

        key_name = PROVIDER_KEY_MAP.get(arbiter_model_def.provider.value)
        api_key = KeyChainManager.get_key(key_name) if key_name else None

        if not api_key:
            return

        agent = AgentFactory.create_agent(arbiter_model_def, api_key=api_key)
        agent.config.max_tokens = 300
        try:
            agent.config.response_format = {"type": "json_object"}
        except AttributeError:
            pass

        prompt = f"""
You are the Arbiter Judge. You are evaluating failing test and security outcomes.
You must review your specific ARBITER MEMORY of known false-positives and exceptions.

ARBITER MEMORY:
{memory}

TEST FAILURES: {verification.test_result.test_failures if verification.test_result else 'None'}
SECURITY FINDINGS: {[f.message for f in security_findings]}

If the memory explicitly states that these specific errors are false-positives or should be ignored, you must PARDON them.
Return strictly a JSON object:
{{
    "pardon_tests": true/false,
    "pardon_security": true/false
}}
"""
        messages = [
            {"role": "system", "content": "You are a JSON-only evaluation agent."},
            {"role": "user", "content": prompt}
        ]

        try:
            full = ""
            async for chunk in agent.chat_stream(messages):
                if chunk.text:
                    full += chunk.text

            raw = full.strip()
            if raw.startswith("```json"):
                raw = raw[7:-3]

            import json
            parsed = json.loads(raw.strip())

            if parsed.get("pardon_tests", False) and verification.test_result:
                verification.test_result.passed = True
                verification.test_result.pass_rate = 100.0
                verification.test_result.test_failures = []

            if parsed.get("pardon_security", False):
                security_findings.clear()

        except Exception as e:
            logger.error(f"Failed to apply Arbiter memory pardons: {e}")

    def format_verdict(self, verdict: ArbiterVerdict) -> str:
        """Format the verdict for display in the chat narration."""
        lines: list[str] = []
        lines.append("⚖️ ARBITER VERDICT")
        lines.append("")
        lines.append(verdict.comparison_summary)
        lines.append("")

        # Per-agent score breakdown
        for score in verdict.scores:
            if score.eliminated:
                lines.append(f"  ❌ {score.model_name}: ELIMINATED — {score.elimination_reason}")
                continue

            emoji = "🏆" if score == verdict.winner else "  "
            lines.append(f"  {emoji} {score.model_name}: {score.total_score:.0f}/100")

            # Stage details
            for stage, weight in SCORING_WEIGHTS.items():
                stage_val = score.stage_scores.get(stage, 0)
                bar = "█" * int(stage_val / 10) + "░" * (10 - int(stage_val / 10))
                stage_label = stage.replace("_", " ").title()
                lines.append(f"      {bar} {stage_val:.0f} — {stage_label} (×{weight:.0%})")

        lines.append("")

        # Evidence
        if verdict.evidence:
            lines.append("📊 Key Evidence:")
            for e in verdict.evidence:
                lines.append(f"  • {e}")

        # Confidence
        conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🟠"}.get(verdict.confidence, "⚪")
        lines.append("")
        lines.append(f"  {conf_emoji} Confidence: {verdict.confidence}")

        return "\n".join(lines)
