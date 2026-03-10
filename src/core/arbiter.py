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

    # Cost tracking
    cost_usd: float = 0.0

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
        intent: str = "edit",
    ) -> ArbiterVerdict:
        """
        Run the 6-stage evaluation pipeline on all agent solutions.

        Args:
            dispatch: The completed ParallelDispatch with agent results
            project_root: Path to the project root directory
            language: Primary language of the project ("python", "typescript", etc.)
            test_command: Custom test command override (e.g., "pytest tests/")
            on_progress: Optional callback(stage_name, agent_id, detail) for narration
            intent: The task intent used for dynamic weighting (e.g., "edit", "chat").

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
                    current_app.post_message(
                        AgentStatusUpdate(
                            agent_id="arbiter",
                            model_name="Arbiter",
                            status="thinking",
                            detail="Reading arbiter memory rules...",
                        )
                    )
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

            structural_score, structural_reason = self._stage1_structural(slot.patch_set, project_root)
            score.stage_scores["structural_validity"] = structural_score

            if structural_score == 0:
                score.eliminated = True
                score.elimination_reason = structural_reason or "Code has syntax errors or diff doesn't apply cleanly"
                score.total_score = 0
                scores.append(score)
                continue

            # ═══════════════════════════════════════════════════
            # AST-Aware Bypassing (Python)
            # ═══════════════════════════════════════════════════
            ast_changed = True
            if language == "python" and slot.patch_set.patches:
                try:
                    import ast

                    ast_changed_any = False
                    for fp in slot.patch_set.patches:
                        if not fp.file_path.endswith(".py") or fp.is_new_file:
                            ast_changed_any = True
                            break

                        full_path = project_root / fp.file_path
                        original_text = full_path.read_text(errors="replace")

                        lines = original_text.splitlines()
                        for hunk in sorted(fp.hunks, key=lambda h: h.start_line, reverse=True):
                            lines[hunk.start_line - 1 : hunk.end_line] = hunk.modified_lines
                        patched_text = "\n".join(lines)

                        orig_ast = ast.dump(ast.parse(original_text))
                        new_ast = ast.dump(ast.parse(patched_text))

                        if orig_ast != new_ast:
                            ast_changed_any = True
                            break
                    ast_changed = ast_changed_any
                except Exception as e:
                    logger.debug(f"AST comparison failed (falling back to testing): {e}")
                    ast_changed = True

            # ═══════════════════════════════════════════════════
            # STAGES 2-4: Run in PARALLEL (lint, tests, security)
            # ═══════════════════════════════════════════════════
            if not ast_changed:
                if on_progress:
                    await on_progress(
                        "verification",
                        slot.agent_id,
                        "AST unchanged. Running local lint + security (skipping tests).",
                    )
                # TRUTHFUL: No tests were run. Report 0/0.
                # Must still run linter and security to catch whitespace errors and secrets in comments.
                from src.tools.sandbox import TestResult, VerificationResult

                verification_result = await self._sandbox._verify_local_only(
                    slot.patch_set,
                    project_root,
                    language,
                    VerificationResult(
                        agent_id=slot.agent_id,
                        model_name=slot.model_name,
                        syntax_valid=True,
                        test_result=TestResult(total=0, passed=0),  # Honest: no tests run
                    ),
                )

                # IMPORTANT: Run security scan even on comment-only changes
                security_findings = await self._security.scan_patch(slot.patch_set, language)

                # LSP would be identical if AST is identical
                if self._lsp:
                    lsp_task = asyncio.create_task(self._lsp.verify_patch_references(slot.patch_set, language))
                else:
                    lsp_task = None
            else:
                if on_progress:
                    await on_progress("verification", slot.agent_id, "Running lint + tests + security scan...")

                def handle_stdout(text: str):
                    if on_progress:
                        import asyncio

                        asyncio.create_task(on_progress("verify_stream", slot.agent_id, text))

                def handle_stderr(text: str):
                    if on_progress:
                        import asyncio

                        asyncio.create_task(on_progress("verify_stream", slot.agent_id, f"ERR: {text}"))

                # Stage 2+3: Sandbox verification (lint + tests)
                sandbox_task = asyncio.create_task(
                    self._sandbox.verify_patch(
                        slot.patch_set,
                        project_root,
                        language,
                        test_command,
                        on_stdout=handle_stdout,
                        on_stderr=handle_stderr,
                    )
                )

                # Stage 4: Security scan
                security_task = asyncio.create_task(self._security.scan_patch(slot.patch_set, language))

                # LSP reference verification (bonus check, runs in parallel too)
                lsp_task = None
                if self._lsp:
                    lsp_task = asyncio.create_task(self._lsp.verify_patch_references(slot.patch_set, language))

                # Await all parallel checks
                verification_result, security_findings = await asyncio.gather(sandbox_task, security_task)

            # Phase 19: Dynamically pardon false-positives using Arbiter Memory
            if arbiter_memory and (verification_result.test_result or security_findings):
                await self._apply_memory_pardons(verification_result, security_findings, arbiter_memory)

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
            test_score = 0.0
            if verification_result.test_result and verification_result.test_result.total > 0:
                test_score = verification_result.test_result.pass_rate
            # Wire TesterAgent: generate + run targeted tests from the diff
            try:
                from src.agents.tester_agent import TesterAgent

                tester = TesterAgent()
                diff_text = slot.response_text[:5000] if slot.response_text else ""
                if diff_text and slot.patch_set and slot.patch_set.file_count > 0:
                    tester_result = await tester.generate_and_run_tests(
                        diff_text=diff_text,
                        language=language,
                        project_root=str(project_root) if project_root else ".",
                    )
                    if tester_result.passed + tester_result.failed > 0:
                        # Blend TesterAgent results with existing test score (60/40 weight)
                        tester_score = tester_result.pass_rate
                        test_score = (test_score * 0.6) + (tester_score * 0.4)
                        logger.info(
                            f"TesterAgent: {tester_result.passed}P/{tester_result.failed}F → blended score {test_score:.1f}"
                        )  # noqa: E501
            except Exception as e:
                logger.debug(f"TesterAgent invocation skipped: {e}")
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
            linter_clean = bool(
                verification_result.lint_result and getattr(verification_result.lint_result, "new_violations", 0) == 0
            )  # noqa: E501
            if linter_clean:
                confidence += 0.2

            # Test check
            tests_passed = False
            if verification_result.test_result:
                if verification_result.test_result.total > 0:
                    tests_passed = bool(getattr(verification_result.test_result, "all_passed", False))

            if tests_passed:
                confidence += 0.3
            elif not ast_changed:
                # If AST is provably unchanged, it's logically safe.
                # Give equivalent confidence as passing tests, without fabricating a test pass.
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
                calibrated_confidence_score=confidence,
            )

            # Elimination based on Frontier Safety Rules
            if confidence < 0.85:
                score.eliminated = True
                score.elimination_reason = (
                    f"Low confidence ({confidence:.2f}): Failed strict verification proofs (tests/lint/security)."  # noqa: E501
                )
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
                        agent_output=slot.response_text[:500] if slot.response_text else "",
                        failure_reason=str(score.elimination_reason),
                        task_id=dispatch.dispatch_id,
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
        weights = self._get_weights_for_intent(intent)
        for s in non_eliminated:
            s.total_score = sum(s.stage_scores.get(stage, 0) * weight for stage, weight in weights.items())

        # Sort by total score (best first)
        scores.sort(key=lambda s: (not s.eliminated, s.total_score), reverse=True)

        # Produce verdict
        total_ms = int((time.time() - eval_start) * 1000)
        verdict = self._produce_verdict(dispatch.dispatch_id, scores, total_ms)

        # ═══════════════════════════════════════════════════
        # ELO FEEDBACK: Push results to EloTracker + Router
        # ═══════════════════════════════════════════════════
        try:
            from src.core.elo_tracker import EloTracker
            from src.core.router import CodingRouter

            if verdict.winner:
                winner_id = verdict.winner.model_id
                loser_ids = [s.model_id for s in scores if s.model_id != winner_id and not s.eliminated]

                # ANTI-GAMING: Skip ELO update if only 1 agent participated
                # Single-agent runs shouldn't distort rankings
                if not loser_ids:
                    logger.debug("Skipping ELO update: single-agent run, no comparison")
                else:
                    costs = {s.model_id: s.cost_usd for s in scores}

                    elo = EloTracker()
                    # Clamp complexity to [1, 10] range
                    task_complexity = max(1, min(10, getattr(dispatch, "complexity", 5)))
                    elo.record_match(
                        winner_id=winner_id,
                        loser_ids=loser_ids,
                        complexity=task_complexity,
                        duration_sec=total_ms / 1000.0,
                        costs=costs,
                    )

                    router = CodingRouter()
                    for s in scores:
                        router.record_outcome(
                            task_id=dispatch.dispatch_id,
                            model_id=s.model_id,
                            intent="edit",
                            complexity=task_complexity,
                            success=(s.model_id == winner_id),
                            error_message=s.elimination_reason if s.eliminated else None,
                        )
                    logger.info(f"ELO feedback pushed: winner={winner_id}, losers={loser_ids}")
        except Exception as e:
            logger.debug(f"ELO feedback push failed (non-critical): {e}")

        if on_progress:
            await on_progress("verdict", "", verdict.comparison_summary)

        return verdict

    # ═════════════════════════════════════════════════════════
    # STAGE IMPLEMENTATIONS
    # ═════════════════════════════════════════════════════════

    def _get_weights_for_intent(self, intent: str) -> dict[str, float]:
        """Dynamic Arbiter weighting based on TaskIntent."""
        if intent == "create":
            return {
                "structural_validity": 0.20,
                "lint_cleanliness": 0.20,
                "test_pass_rate": 0.30,
                "security_score": 0.20,
                "diff_minimality": 0.05,
                "complexity_delta": 0.05,
            }
        elif intent == "chat" or intent == "question":
            return {
                "structural_validity": 0.80,  # Just don't break the syntax
                "lint_cleanliness": 0.10,
                "test_pass_rate": 0.0,
                "security_score": 0.10,
                "diff_minimality": 0.0,
                "complexity_delta": 0.0,
            }
        # Default (edit/debug/architect)
        return {
            "structural_validity": 0.10,
            "lint_cleanliness": 0.10,
            "test_pass_rate": 0.40,
            "security_score": 0.20,
            "diff_minimality": 0.10,
            "complexity_delta": 0.10,
        }

    def _stage1_structural(self, patch_set: PatchSet, project_root: Path) -> tuple[float, str | None]:
        """
        Stage 1: Structural Validation.
        Check that diffs apply cleanly and code is syntactically valid.
        Returns (score, error_reason).
        """
        for fp in patch_set.patches:
            if not getattr(fp, "syntax_valid", True):
                return 0.0, f"Syntax error in {fp.file_path}: {getattr(fp, 'syntax_error', 'Invalid syntax')}"

            full_path = project_root / fp.file_path

            # Check: does the file exist (for modifications, not new files)?
            if not fp.is_new_file and not full_path.exists():
                logger.warning(f"Structural: {fp.file_path} does not exist")
                return 0.0, f"File {fp.file_path} does not exist"

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
                            return 0.0, f"Hunk range out of bounds in {fp.file_path}"
                except Exception as e:
                    logger.warning(f"Structural: can't read {fp.file_path}: {e}")
                    return 0.0, f"Can't read {fp.file_path}"

            # Check: is the resulting code syntactically valid? (tree-sitter)
            try:
                # Build what the file would look like after applying this patch
                if fp.is_new_file:
                    patched_content = "\n".join(line for hunk in fp.hunks for line in hunk.modified_lines)
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
                return 0.0, f"Syntax error in {fp.file_path}: {e}"
            except Exception:
                pass  # Non-Python files: skip syntax check, rely on lint

        return 100.0, None

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
        Stage 6: Measure cyclomatic complexity delta using AST for Python,
        keyword heuristic for other languages.
        """
        import ast as _ast

        stats = ComplexityStats()

        # AST node types that increase cyclomatic complexity
        BRANCH_NODES = (
            _ast.If,
            _ast.For,
            _ast.While,
            _ast.ExceptHandler,
            _ast.With,
            _ast.Assert,
            _ast.BoolOp,
        )
        # Python 3.10+
        try:
            BRANCH_NODES = BRANCH_NODES + (_ast.Match,)
        except AttributeError:
            pass

        branch_keywords_js = re.compile(r"\b(if|else|for|while|catch|switch|case|\&\&|\|\||\?)\b")

        total_before = 0
        total_after = 0
        max_nesting_before = 0
        max_nesting_after = 0

        def _ast_complexity(code: str) -> tuple[int, int]:
            """Return (branch_count, max_nesting) from AST analysis."""
            try:
                tree = _ast.parse(code)
            except SyntaxError:
                return 0, 0

            branches = sum(1 for node in _ast.walk(tree) if isinstance(node, BRANCH_NODES))
            nesting = _max_nesting(tree, 0)
            return branches, nesting

        def _max_nesting(node, depth: int) -> int:
            """Recursively find maximum nesting depth in AST."""
            max_d = depth
            for child in _ast.iter_child_nodes(node):
                if isinstance(child, BRANCH_NODES):
                    max_d = max(max_d, _max_nesting(child, depth + 1))
                else:
                    max_d = max(max_d, _max_nesting(child, depth))
            return max_d

        for fp in patch_set.patches:
            ext = Path(fp.file_path).suffix.lower() if fp.file_path else ""
            is_python = ext in (".py", ".pyi")

            for hunk in fp.hunks:
                if is_python:
                    # Use real AST analysis
                    before_code = "\n".join(hunk.original_lines)
                    after_code = "\n".join(hunk.modified_lines)
                    b_branches, b_nesting = _ast_complexity(before_code)
                    a_branches, a_nesting = _ast_complexity(after_code)
                    total_before += b_branches
                    total_after += a_branches
                    max_nesting_before = max(max_nesting_before, b_nesting)
                    max_nesting_after = max(max_nesting_after, a_nesting)
                else:
                    # Fallback: keyword heuristic for JS/TS/etc.
                    keywords = (
                        branch_keywords_js
                        if ext in (".js", ".jsx", ".ts", ".tsx")
                        else re.compile(r"\b(if|elif|else|for|while|except|and|or|case|match)\b")
                    )
                    for line in hunk.original_lines:
                        total_before += len(keywords.findall(line))
                        indent = len(line) - len(line.lstrip())
                        max_nesting_before = max(max_nesting_before, indent // 4)
                    for line in hunk.modified_lines:
                        total_after += len(keywords.findall(line))
                        indent = len(line) - len(line.lstrip())
                        max_nesting_after = max(max_nesting_after, indent // 4)

        hunk_count = max(patch_set.total_hunks, 1)
        stats.avg_complexity_before = total_before / hunk_count
        stats.avg_complexity_after = total_after / hunk_count
        stats.max_nesting_before = max_nesting_before
        stats.max_nesting_after = max_nesting_after

        return stats

    # ═════════════════════════════════════════════════════════
    # VERDICT GENERATION
    # ═════════════════════════════════════════════════════════

    def _produce_verdict(self, dispatch_id: str, scores: list[ArbiterScore], total_ms: int) -> ArbiterVerdict:
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
                evidence.append(f"{winner.model_name} {w_dir} complexity. {runner_up.model_name} {r_dir} complexity.")

            # LSP reference check
            if winner.reference_verification and not winner.reference_verification.complete:
                evidence.append(
                    f"⚠️ {winner.model_name} missed {len(winner.reference_verification.missed)} cross-file references."
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

    def _apply_deterministic_exemptions(
        self,
        verification: VerificationResult,
        security_findings: list[SecurityFinding],
        exemptions: list[dict],
    ) -> None:
        """
        Apply only explicit, user-authored exemptions.

        Unlike the old LLM-based pardons, this method:
        - Only removes findings that match exemption rules by rule_id
        - Never overrides test failures
        - Requires human-authored exemption entries
        """
        if not exemptions:
            return

        for exemption in exemptions:
            rule = exemption.get("rule")
            reason = exemption.get("reason", "user exemption")
            if rule:
                before_count = len(security_findings)
                security_findings[:] = [
                    f for f in security_findings if not (hasattr(f, "rule_id") and f.rule_id == rule)
                ]
                removed = before_count - len(security_findings)
                if removed > 0:
                    logger.info(f"Exempted {removed} security finding(s) matching rule '{rule}': {reason}")

    async def _apply_memory_pardons(
        self,
        verification: VerificationResult,
        security_findings: list[SecurityFinding],
        arbiter_memory: str,
    ) -> None:
        """
        Deterministically apply user-authored exemptions from arbiter memory.

        SECURITY: Only `low` and `info` severity findings can be pardoned.
        Medium/high/critical findings are immune to memory exemptions.

        Expected format lines in memory:
        - `EXEMPT_RULE:<rule_id> reason...`
        """
        exemptions: list[dict] = []
        for line in arbiter_memory.splitlines():
            stripped = line.strip()
            if not stripped.startswith("EXEMPT_RULE:"):
                continue
            _, rule_and_reason = stripped.split("EXEMPT_RULE:", 1)
            rule_and_reason = rule_and_reason.strip()
            if not rule_and_reason:
                continue
            parts = rule_and_reason.split(" ", 1)
            rule = parts[0].strip()
            reason = parts[1].strip() if len(parts) > 1 else "arbiter memory exemption"
            exemptions.append({"rule": rule, "reason": reason})

        if not exemptions:
            return

        # Filter out findings that are too severe to pardon
        pardonable_findings = [f for f in security_findings if f.severity in ("low", "info")]
        non_pardonable = [f for f in security_findings if f.severity not in ("low", "info")]

        if pardonable_findings:
            self._apply_deterministic_exemptions(verification, pardonable_findings, exemptions)

        # Log if user tried to pardon high-severity findings
        if non_pardonable:
            for ex in exemptions:
                for f in non_pardonable:
                    if f.rule_id == ex["rule"]:
                        logger.warning(
                            f"Memory pardon BLOCKED: cannot exempt {f.severity} "
                            f"finding '{f.rule_id}' — only low/info severity can be pardoned"
                        )

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
