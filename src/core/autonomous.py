"""
Autonomous project execution engine.

Reads a project plan, breaks it into subtasks, and drives the
multi-agent loop (Coder → Tester → Arbiter) until the project
is complete or budget is exhausted.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from src.core.agent_bus import AgentMessage, AgentMessageBus
from src.core.logger import get_logger
from src.core.workspace import Workspace

logger = get_logger("core.autonomous")


@dataclass
class SubtaskResult:
    """Result of a single Coder → Tester → Arbiter cycle."""

    subtask: str
    approved: bool = False
    code_output: str = ""
    test_output: str = ""
    arbiter_feedback: str = ""
    cost_usd: float = 0.0
    tokens_used: int = 0
    attempts: int = 0


@dataclass
class AutonomousState:
    """Persistent state for the autonomous runner."""

    goal: str = ""
    plan_path: str = ".gptcgt/project_plan.md"
    current_iteration: int = 0
    total_cost: float = 0.0
    total_tokens: int = 0
    completed_subtasks: list[str] = field(default_factory=list)
    failed_subtasks: list[str] = field(default_factory=list)
    is_running: bool = False
    is_paused: bool = False


class AutonomousRunner:
    """
    Long-running project loop. Reads a plan, breaks it into subtasks,
    and drives the DAG engine in a loop until done or budget exhausted.

    Flow per iteration:
    1. Read .gptcgt/project_plan.md → find next uncompleted subtask
    2. Run Coder Agent (produces code)
    3. Run Tester Agent (validates code health)
    4. Run Arbiter Agent (judges quality: pass/fail/improve)
    5. If fail → feed fix suggestions back to Coder (max 3 attempts)
    6. If pass → mark subtask done, update plan file, next subtask
    7. Budget check between every iteration
    """

    def __init__(self, bus: AgentMessageBus | None = None) -> None:
        self.bus = bus or AgentMessageBus()
        self.state = AutonomousState()
        self._cancel_event: asyncio.Event | None = None

    async def run(
        self,
        goal: str,
        narration_callback=None,
        yield_chunk_callback=None,
        error_callback=None,
        cancel_event: asyncio.Event | None = None,
    ) -> None:
        """
        Execute the autonomous loop.  # noqa: D213

        Args:  # noqa: D413
            goal: The user's high-level objective (e.g. "Build a GTA-style game")
            narration_callback: Callback to narrate progress to the chat
            yield_chunk_callback: Callback to stream text chunks to the UI
            error_callback: Callback to report errors
            cancel_event: Event to signal cancellation
        """
        self.state.goal = goal
        self.state.is_running = True
        self._cancel_event = cancel_event

        try:
            # Phase 1: Generate the plan
            self.bus.send(AgentMessage(
                "orchestrator", "all",
                f"Starting autonomous mode: '{goal}'",
                msg_type="system",
            ))

            if narration_callback:
                await narration_callback("🚀 Autonomous mode started", "info")

            # Generate or read existing plan
            plan_text = await self._ensure_plan(goal, narration_callback)
            subtasks = self._parse_subtasks(plan_text)

            if narration_callback:
                await narration_callback(
                    f"📋 Plan created with {len(subtasks)} subtasks", "info"
                )

            # Phase 2: Execute subtasks
            for i, subtask in enumerate(subtasks):
                if self._is_cancelled():
                    self.bus.send(AgentMessage(
                        "orchestrator", "all", "Autonomous mode cancelled by user.",
                        msg_type="system",
                    ))
                    break

                if self.state.is_paused:
                    self.bus.send(AgentMessage(
                        "orchestrator", "all", "Autonomous mode paused. Waiting for user.",
                        msg_type="system",
                    ))
                    break

                # Budget check
                if self._check_budget_exceeded():
                    self.bus.send(AgentMessage(
                        "orchestrator", "all",
                        f"Budget limit reached (${self.state.total_cost:.2f}). Pausing.",
                        msg_type="system",
                    ))
                    if narration_callback:
                        await narration_callback(
                            f"⚠️ Budget limit reached. ${self.state.total_cost:.2f} spent.",
                            "warning",
                        )
                    break

                # Iteration limit check
                max_iter = self._get_max_iterations()
                if i >= max_iter:
                    self.bus.send(AgentMessage(
                        "orchestrator", "all",
                        f"Iteration limit ({max_iter}) reached. Pausing.",
                        msg_type="system",
                    ))
                    break

                self.state.current_iteration = i + 1
                self.bus.start_iteration(i + 1)

                if narration_callback:
                    await narration_callback(
                        f"[Iteration {i+1}/{len(subtasks)}] {subtask[:60]}...",
                        "info",
                    )

                # Execute subtask with retry loop
                result = await self._execute_subtask(subtask, i + 1)

                if result.approved:
                    self.state.completed_subtasks.append(subtask)
                    self._update_plan_status(subtask, "done")
                else:
                    self.state.failed_subtasks.append(subtask)
                    self._update_plan_status(subtask, "failed")

                self.state.total_cost += result.cost_usd
                self.state.total_tokens += result.tokens_used

            # Phase 3: Summary
            self.bus.send(AgentMessage(
                "orchestrator", "all",
                f"Autonomous mode finished. "
                f"{len(self.state.completed_subtasks)} done, "
                f"{len(self.state.failed_subtasks)} failed, "
                f"${self.state.total_cost:.2f} spent.",
                msg_type="system",
            ))

        except asyncio.CancelledError:
            logger.info("Autonomous mode cancelled")
        except Exception as e:
            logger.error(f"Autonomous mode error: {e}", exc_info=True)
            if error_callback:
                await error_callback(str(e))
        finally:
            self.state.is_running = False

    async def _ensure_plan(self, goal: str, narration_callback) -> str:
        """Generate a project plan via LLM or read an existing one."""
        from src.core.workspace import Workspace
        workspace = Workspace.get_instance()
        plan_path = Path(self.state.plan_path)

        # Check if plan already exists in workspace
        if workspace.safe_exists(plan_path):
            existing = workspace.safe_read(plan_path)
            if existing.strip():
                self.bus.send(AgentMessage(
                    "orchestrator", "all",
                    "Found existing project plan. Resuming.",
                    msg_type="info",
                ))
                return existing

        # Generate plan via the real LLM pipeline
        self.bus.send(AgentMessage(
            "orchestrator", "coder",
            f"Creating detailed project plan for: {goal}",
            msg_type="request",
        ))

        plan_prompt = (
            f"Create a detailed, actionable project plan for the following goal:\n\n"
            f"**Goal:** {goal}\n\n"
            "Format the plan as markdown with:\n"
            "- Phase headers (## Phase N: Name)\n"
            "- Each task as a checkbox: `- [ ] Specific, actionable task description`\n"
            "- Tasks should be small enough for a single coding session (one file or feature)\n"
            "- Include setup, core implementation, error handling, tests, and documentation\n"
            "- Be concrete — mention specific file names, functions, and modules\n"
            "- 8-15 total tasks is ideal\n\n"
            "Output ONLY the markdown plan, nothing else."
        )

        plan_chunks: list[str] = []

        try:
            from src.core.chat_store import ChatStore  # noqa: I001
            from src.core.chat_pipeline import ChatPipeline
            from src.core.model_registry import QualityTier

            # Use a LIGHT model for plan generation to save budget
            from src.core.workspace import Workspace
            ws = Workspace.get_instance()
            planner = ChatPipeline(
                ChatStore(workspace=ws), default_tier=QualityTier.LIGHT,
            )

            async def _capture_chunk(text: str) -> None:
                plan_chunks.append(text)

            await planner.process_message(
                plan_prompt,
                yield_chunk_callback=_capture_chunk,
                cancel_event=self._cancel_event,
                complexity=3,
            )

            plan_text = "".join(plan_chunks).strip()
            if plan_text and "- [ ]" in plan_text:
                # LLM produced a valid plan
                workspace.safe_write(plan_path, plan_text)
                self.bus.send(AgentMessage(
                    "coder", "orchestrator",
                    f"Plan generated with {plan_text.count('- [ ]')} tasks.",
                    msg_type="response",
                ))
                return plan_text

        except Exception as e:
            logger.warning(f"LLM plan generation failed, using skeleton: {e}")

        # Fallback: create a skeleton plan if LLM call failed
        plan = f"# Project Plan: {goal}\n\n"
        plan += "## Phase 1: Foundation\n"
        plan += f"- [ ] Set up project structure for: {goal}\n"
        plan += "- [ ] Create core module scaffolding\n"
        plan += "- [ ] Set up configuration and entry point\n\n"
        plan += "## Phase 2: Core Implementation\n"
        plan += f"- [ ] Implement primary functionality for: {goal}\n"
        plan += "- [ ] Add error handling and validation\n\n"
        plan += "## Phase 3: Testing & Polish\n"
        plan += "- [ ] Write tests for core functionality\n"
        plan += "- [ ] Code review and optimization\n"
        plan += "- [ ] Documentation\n"

        workspace.safe_write(plan_path, plan)
        return plan

    def _parse_subtasks(self, plan_text: str) -> list[str]:
        """Extract uncompleted subtasks from the plan markdown."""
        subtasks = []
        for line in plan_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("- [ ]"):
                task = stripped[5:].strip()
                if task:
                    subtasks.append(task)
            elif stripped.startswith("- [/]"):
                # In-progress tasks should also be picked up
                task = stripped[5:].strip()
                if task:
                    subtasks.append(task)
        return subtasks

    async def _execute_subtask(self, subtask: str, iteration: int) -> SubtaskResult:
        """Execute one Coder → Tester → Arbiter cycle with retries."""
        from src.core.chat_pipeline import ChatPipeline
        from src.core.chat_store import ChatStore
        from src.core.diff_engine import DiffExtractor, PatchEngine
        from src.core.model_registry import ModelRegistry, QualityTier

        result = SubtaskResult(subtask=subtask)
        max_attempts = 3
        feedback = ""
        registry = ModelRegistry()  # noqa: F841

        for attempt in range(max_attempts):
            if self._is_cancelled():
                break

            result.attempts = attempt + 1

            # ── Step 1: Coder — call real ChatPipeline ──────────────────
            # Per-task budget check
            try:
                import textual.app as _tapp
                app = _tapp.active_app.get()
                if hasattr(app, "config"):
                    per_task_limit = getattr(app.config.user, "max_spend_per_task", 5.0)
                    if result.cost_usd >= per_task_limit:
                        logger.warning(f"Per-task budget limit (${per_task_limit}) reached for '{subtask[:20]}'.")
                        self.bus.send(AgentMessage(
                            "orchestrator", "coder",
                            f"Per-task budget limit (${per_task_limit}) reached. Aborting subtask.",
                            msg_type="error",
                            iteration=iteration,
                        ))
                        break
            except Exception:
                pass

            coder_prompt = (
                f"You are working on an autonomous coding task.\n\n"
                f"**Subtask:** {subtask}\n"
            )
            if feedback:
                coder_prompt += (
                    f"\n**Previous attempt failed.** Here is the feedback:\n"
                    f"{feedback}\n\n"
                    f"Fix the issues and try again."
                )

            self.bus.send(AgentMessage(
                "orchestrator", "coder",
                f"Implement: {subtask}" + (f" (attempt {attempt+1})" if attempt else ""),
                msg_type="request",
                iteration=iteration,
            ))

            response_chunks: list[str] = []
            coder_usage: dict = {"prompt_tokens": 0, "completion_tokens": 0}  # noqa: F841

            async def _chunk_collector(text: str) -> None:
                response_chunks.append(text)

            async def _error_handler(err: str) -> None:
                logger.error(f"Coder error on subtask '{subtask[:40]}': {err}")

            try:
                # Determine tier: use STANDARD for coding tasks
                from src.core.workspace import Workspace
                ws = Workspace.get_instance()
                coder_pipeline = ChatPipeline(
                    ChatStore(workspace=ws), default_tier=QualityTier.STANDARD,
                )

                await coder_pipeline.process_message(
                    coder_prompt,
                    yield_chunk_callback=_chunk_collector,
                    error_callback=_error_handler,
                    cancel_event=self._cancel_event,
                    complexity=7,
                )

            except Exception as e:
                logger.error(f"Coder pipeline failed: {e}")
                self.bus.send(AgentMessage(
                    "coder", "orchestrator",
                    f"Coder failed: {str(e)[:200]}",
                    msg_type="error",
                    iteration=iteration,
                ))
                feedback = f"Coder threw an exception: {str(e)[:500]}"
                continue

            full_response = "".join(response_chunks)
            result.code_output = full_response

            if not full_response.strip():
                self.bus.send(AgentMessage(
                    "coder", "orchestrator",
                    "Coder returned empty response.",
                    msg_type="error",
                    iteration=iteration,
                ))
                feedback = "Empty response from coder. Please generate actual code."
                continue

            # Notify bus with coder completion
            self.bus.send(AgentMessage(
                "coder", "tester",
                f"Implementation complete ({len(full_response)} chars). Please test.",
                msg_type="response",
                iteration=iteration,
            ))

            # ── Step 2: Extract diffs (do NOT apply yet) ────────────────────
            extractor = DiffExtractor()
            patch_set = extractor.extract(
                full_response, agent_id="auto_coder", model_name="autonomous"
            )

            if patch_set.file_count > 0:
                # Post PatchSetProposed to UI for visibility
                try:
                    import textual.app as _tapp  # noqa: I001
                    from src.core.events import PatchSetProposed
                    _tapp.active_app.get().post_message(
                        PatchSetProposed(patch_set=patch_set)
                    )
                except Exception:
                    pass

                # Pre-test: LSP Verification for missed references
                try:
                    from src.tools.lsp import LSPClient
                    workspace = Workspace.get_instance()
                    lsp = LSPClient(workspace.get_project_root())
  # noqa: W293
                    lang = "python"
                    for fp in patch_set.patches:
                        if str(fp.file_path).endswith((".ts", ".tsx", ".js", ".jsx")):
                            lang = "typescript"
                            break
  # noqa: W293
                    verification = await lsp.verify_patch_references(patch_set, lang)
                    if not verification.complete:
                        missed_msg = lsp.format_missed_references(verification)
                        feedback = f"LSP Reference Verification Failed:\n{missed_msg}\nPlease update all references."
                        self.bus.send(AgentMessage(
                            "tester", "coder",
                            f"LSP Verification Failed:\n{missed_msg}",
                            msg_type="feedback",
                            iteration=iteration,
                        ))
                        continue
                except Exception as e:
                    logger.warning(f"LSP Verification skipped or failed: {e}")

            # ── Step 3: Tester — run tests on diffs ─────────────────────
            test_passed = patch_set.file_count == 0
            test_feedback = ""

            if patch_set.file_count > 0:
                try:
                    from src.agents.tester_agent import TesterAgent

                    tester = TesterAgent()
                    workspace = Workspace.get_instance()
                    project_root = str(workspace.get_project_root())

                    # Build diff text from patches for the tester
                    diff_text = patch_set.raw_response or full_response[:3000]

                    # Pass the correctly evaluated language to the tester
                    test_result = await tester.generate_and_run_tests(
                        diff_text=diff_text,
                        language=lang,
                        project_root=project_root,
                    )

                    result.test_output = (
                        f"Passed: {test_result.passed}, "
                        f"Failed: {test_result.failed}, "
                        f"Errors: {test_result.errors}"
                    )

                    # Reject if tests explicitly failed OR if the tester was inconclusive (no keys, no tests generated)
                    if test_result.failed > 0 or test_result.errors > 0 or test_result.is_inconclusive or not test_result.generated_test_code:
                        test_passed = False
                        details = "; ".join(test_result.failure_details[:3])
                        test_feedback = (
                            f"Tests failed or inconclusive ({test_result.failed}F, {test_result.errors}E): "
                            f"{details[:500]}"
                        )
                        self.bus.send(AgentMessage(
                            "tester", "coder",
                            f"Tests failed: {test_feedback[:200]}",
                            msg_type="feedback",
                            iteration=iteration,
                        ))
                    else:
                        self.bus.send(AgentMessage(
                            "tester", "arbiter",
                            f"All {test_result.passed} tests passed. Requesting review.",
                            msg_type="response",
                            iteration=iteration,
                        ))

                except Exception as e:
                    logger.warning(f"TesterAgent skipped: {e}")
                    test_passed = False
                    test_feedback = (
                        "Tester unavailable; cannot verify generated changes safely. "
                        "Configure tester dependencies/API keys and retry."
                    )
                    self.bus.send(AgentMessage(
                        "tester", "arbiter",
                        "Tester unavailable; blocking auto-apply until verification is available.",
                        msg_type="response",
                        iteration=iteration,
                    ))

            if not test_passed:
                feedback = test_feedback or "Automated tests did not pass."
                continue

            # ── Step 4: Arbiter — approve and apply ───────────────────────
            # If we get here, code was generated + tests passed

            if patch_set.file_count > 0:
                verification_badge = "flagged"  # Default to flagged
                if test_passed:
                    try:
                        from src.core.security import SecurityScanner
                        from src.core.workspace import Workspace
                        ws = Workspace.get_instance()
                        project_root = ws.get_project_root()
                        lang = ws.config.project.primary_language or "python"
                        findings = await SecurityScanner().scan_patch(patch_set, lang)
                        has_blocking = any(
                            getattr(f, "severity", "").lower() in ("critical", "high")
                            for f in findings
                        )
                        verification_badge = "clean" if not has_blocking else "flagged"
                        if has_blocking:
                            feedback = "Security scan found high/critical issues. Revise patch."
                        logger.info(f"Arbiter verification: tests passed, security_findings={len(findings)}")
                    except Exception as e:
                        logger.warning(
                            f"Arbiter verification failed: {e}. Blocking auto-apply."
                        )
                        verification_badge = "flagged"
                        feedback = "Arbiter verification failed; patch not applied."

                if verification_badge == "clean":
                    # Mark all hunks as explicitly approved by Arbiter
                    for fp in patch_set.patches:
                        for hunk in fp.hunks:
                            hunk.status = "approved"

                    engine = PatchEngine()
                    try:
                        engine.apply_approved(patch_set)
                        self.bus.send(AgentMessage(
                            "coder", "orchestrator",
                            f"Applied {patch_set.total_hunks} hunks across {patch_set.file_count} files.",
                            msg_type="info",
                            iteration=iteration,
                        ))
                    except Exception as e:
                        logger.warning(f"Patch apply failed: {e}")
                        feedback = f"Patch application failed: {str(e)[:500]}. Fix the diff format."
                        continue
                else:
                    from src.core.events import RequireUserApproval  # noqa: F401
                    self.bus.send(AgentMessage(
                        "arbiter", "orchestrator",
                        "Arbiter flagged changes. Awaiting user approval.",
                        msg_type="feedback",
                        iteration=iteration,
                    ))
                    # Wait for user logic goes here

            self.bus.send(AgentMessage(
                "arbiter", "orchestrator",
                f"Approved. Subtask '{subtask[:40]}' meets quality standards.",
                msg_type="approval",
                iteration=iteration,
            ))

            result.approved = True

            # Track cost from the ChatPipeline
            try:
                import textual.app as _tapp
                app = _tapp.active_app.get()
                if hasattr(app, "cost_tracker"):
                    today = app.cost_tracker.get_today_spend()
                    result.cost_usd = today.total_cost - self.state.total_cost
            except Exception:
                pass

            break

        return result

    def _update_plan_status(self, subtask: str, status: str) -> None:
        """Update the plan file to mark a subtask as done or failed."""
        try:
            workspace = Workspace.get_instance()
            plan_path = Path(self.state.plan_path)
            if not workspace.safe_exists(plan_path):
                return

            content = workspace.safe_read(plan_path)
            if status == "done":
                content = content.replace(f"- [ ] {subtask}", f"- [x] {subtask}")
                content = content.replace(f"- [/] {subtask}", f"- [x] {subtask}")
            elif status == "failed":
                content = content.replace(f"- [ ] {subtask}", f"- [!] {subtask} (FAILED)")
            workspace.safe_write(plan_path, content)
        except Exception as e:
            logger.warning(f"Could not update plan: {e}")

    def _check_budget_exceeded(self) -> bool:
        """
        Check if total autonomous SESSION cost exceeds the session budget.

        Uses max_autonomous_budget for the entire session cap.
        Per-task budget (max_spend_per_task) is checked inside _execute_subtask.
        """
        try:
            import textual.app as _tapp
            current_app = _tapp.active_app.get()
            if hasattr(current_app, "config"):
                session_limit = getattr(
                    current_app.config.user,
                    "max_autonomous_budget",
                    20.0,
                )
                return self.state.total_cost >= session_limit
        except Exception:
            pass
        return False

    def _get_max_iterations(self) -> int:
        """Get the max iterations from config."""
        try:
            import textual.app as _tapp
            current_app = _tapp.active_app.get()
            if hasattr(current_app, "config"):
                return getattr(current_app.config.user, "max_autonomous_iterations", 50)
        except Exception:
            pass
        return 50

    def _is_cancelled(self) -> bool:
        """Check if the user cancelled."""
        if self._cancel_event and self._cancel_event.is_set():
            return True
        return False

    def pause(self) -> None:
        """Pause the autonomous loop."""
        self.state.is_paused = True
        self.bus.send(AgentMessage(
            "orchestrator", "all", "Autonomous mode paused by user.",
            msg_type="system",
        ))

    def resume(self) -> None:
        """Resume the autonomous loop."""
        self.state.is_paused = False
        self.bus.send(AgentMessage(
            "orchestrator", "all", "Autonomous mode resumed.",
            msg_type="system",
        ))
