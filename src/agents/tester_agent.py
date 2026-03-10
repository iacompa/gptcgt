"""
Independent Tester Agent.

A standalone agent that receives code diffs, generates targeted test cases,
runs them in the E2B sandbox, and maintains its own memory file at
`.gptcgt/agents/tester.md`.

This replaces the embedded test stage inside the Arbiter with a first-class
agent that can be routed to independently and can communicate results
back to the orchestrator and arbiter.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.logger import get_logger

logger = get_logger("agents.tester_agent")


@dataclass
class TestResult:
    """Structured result from the TesterAgent."""

    passed: int = 0
    failed: int = 0
    errors: int = 0
    coverage_delta: float = 0.0
    failure_details: list[str] = field(default_factory=list)
    generated_test_code: str = ""
    is_inconclusive: bool = False  # True when tests could not be run (no keys, etc)

    @property
    def pass_rate(self) -> float:
        total = self.passed + self.failed + self.errors
        return (self.passed / total * 100) if total > 0 else 0.0


TestResult.__test__ = False


class TesterAgent:
    """
    Independent agent that:
    1. Receives a diff/patch from the coder
    2. Generates targeted test cases for the changed code
    3. Runs them in the sandbox
    4. Reports results and updates its own memory file
    """

    __test__ = False
    MAX_TEST_GEN_TOKENS = 2000

    def __init__(self) -> None:
        from src.core.model_registry import ModelRegistry

        self.registry = ModelRegistry()

    async def generate_and_run_tests(
        self,
        diff_text: str,
        language: str = "python",
        test_command: str = "pytest",
        project_root: str = ".",
    ) -> TestResult:
        """
        Full pipeline: generate tests → run in sandbox → report results.
        Uses an adaptive loop to self-heal breaking tests and improve coverage.
        """
        result = TestResult()
        available = self.registry.get_available_models()
        if not available:
            logger.warning("TesterAgent: No API keys configured — cannot generate tests.")
            result.is_inconclusive = True
            return result

        from src.core.system_prompt import SystemPromptBuilder

        system_prompt = SystemPromptBuilder.build(
            role_type="engineer",
            custom_instructions=(
                f"You are a senior test engineer. Given a code diff in {language}, "
                "generate focused unit tests that cover the changed lines. "
                "Output ONLY the test code. Do not output markdown codeblocks, just the raw code. "
                "No explanations. "
                "If test execution output is returned, read the failure or coverage report "
                "and rewrite the test code to fix the issues."
            ),
            model_name="tester",
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"DIFF:\n{diff_text[:3000]}"},
        ]

        test_code = ""
        max_iterations = 3

        # Inject coverage if using pytest
        dynamic_test_cmd = test_command
        if language == "python" and "pytest" in test_command:
            dynamic_test_cmd = f"pip install pytest-cov -q && {test_command} --cov --cov-report=term-missing"

        from pathlib import Path as PathLib

        from src.core.diff_engine import FilePatch, Hunk, PatchSet
        from src.tools.sandbox import E2BSandbox

        sandbox = E2BSandbox()

        for iteration in range(max_iterations):
            test_code = await self._generate_tests_multi_turn(messages, language, available)
            if not test_code:
                logger.warning(f"TesterAgent: No test code generated on iteration {iteration}.")
                break

            # Strip backticks if returned
            test_code = test_code.replace("```python", "").replace("```", "").strip()

            result.generated_test_code = test_code

            # 2. Run tests in sandbox
            try:
                test_patch = FilePatch(
                    file_path=f"tests/test_generated_{hash(test_code) % 10000}.py",
                    is_new_file=True,
                    hunks=[
                        Hunk(
                            start_line=1,
                            end_line=1,
                            original_lines=[],
                            modified_lines=test_code.splitlines(),
                            status="approved",
                        )
                    ],
                )
                test_patch_set = PatchSet(
                    patches=[test_patch],
                    agent_id="tester_agent",
                    model_name="tester",
                    raw_response=test_code,
                )
                verification = await sandbox.verify_patch(
                    test_patch_set,
                    PathLib(project_root),
                    language,
                    test_command=dynamic_test_cmd,
                )

                if verification and verification.test_result:
                    tr = verification.test_result
                    result.passed = tr.passed
                    result.failed = tr.failed
                    result.errors = tr.errors
                    result.failure_details.clear()

                    # Surface full stderr/raw output
                    if tr.raw_output and (result.failed > 0 or result.errors > 0):
                        result.failure_details.append(tr.raw_output[:2000])
                    else:
                        result.failure_details = [
                            f.get("message", str(f)) if isinstance(f, dict) else str(f) for f in (tr.failures or [])
                        ]

                    # Adaptive Loop decision
                    if result.failed > 0 or result.errors > 0:
                        logger.info(f"TesterAgent Loop {iteration}: {result.failed}F {result.errors}E. Self-healing...")
                        messages.append({"role": "assistant", "content": test_code})
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    f"The test run failed. Here is the output:\n{tr.raw_output[:2000]}\n"
                                    "Please FIX the code to pass and improve coverage. RETURN ONLY THE RAW CODE."
                                ),
                            }
                        )
                        continue
                    else:
                        logger.info(f"TesterAgent Loop {iteration}: All tests passed!")
                        break

            except Exception as e:
                logger.error(f"TesterAgent sandbox execution failed: {e}")
                result.errors = 1
                result.failure_details.append(str(e))
                break

        # 3. Update tester memory
        if result.failed > 0 or result.errors > 0:
            await self._update_memory(diff_text, result)

        return result

    async def _generate_tests_multi_turn(self, messages: list[dict], language: str, available_models: list) -> str:
        """Use configured tester model, then fallback to cheapest model to generate targeted tests."""
        try:
            if not available_models:
                logger.warning("TesterAgent: No models available to generate tests.")
                return ""

            from src.core.config import ConfigManager

            config = ConfigManager.get_instance()
            tester_model_id = config.user.tester_model

            selected_model = None

            # 1. Explicit tester override
            if tester_model_id:
                for m in available_models:
                    if m.id == tester_model_id:
                        selected_model = m
                        break
                if not selected_model:
                    logger.warning(f"Configured tester model {tester_model_id} not available. Falling back.")

            # 2. Fallback to cheapest
            if not selected_model:
                selected_model = sorted(available_models, key=lambda x: x.input_cost_per_mtok)[0]

            from src.agents.factory import PROVIDER_KEY_MAP, AgentFactory
            from src.auth.keychain import KeyChainManager
            from src.core.model_registry import Provider

            key_name = PROVIDER_KEY_MAP.get(selected_model.provider.value)
            api_key = KeyChainManager.get_key(key_name) if key_name else None
            # noqa: W293
            # Support Custom models without keys
            if not api_key:
                if selected_model.provider == Provider.CUSTOM and not getattr(
                    selected_model, "api_key_required", False
                ):  # noqa: E501
                    pass  # Keep going
                else:
                    logger.warning(f"TesterAgent: Missing key for {selected_model.id}")
                    return ""

            agent = AgentFactory.create_agent(
                selected_model,  # noqa: W291
                api_key=api_key,  # noqa: W291
                base_url=getattr(selected_model, "base_url", None),
            )
            agent.config.max_tokens = self.MAX_TEST_GEN_TOKENS

            full_response = ""
            async for chunk in agent.chat_stream(messages):
                if chunk.text:
                    full_response += chunk.text

            return full_response.strip()

        except Exception as e:
            logger.error(f"TesterAgent test generation failed: {e}")
            return ""

    async def _update_memory(self, diff_text: str, result: TestResult) -> None:
        """Append learning to .gptcgt/agents/tester.md."""
        try:
            from src.core.workspace import Workspace

            ws = Workspace.get_instance()
            memory_path = ".gptcgt/agents/tester.md"

            existing = ""
            if ws.safe_exists(memory_path):
                existing = ws.safe_read(memory_path)

            # Only record meaningful results
            if result.failed > 0 or result.errors > 0:
                entry = (
                    f"\n- **Test Failure** ({result.failed} failed, {result.errors} errors): "
                    f"{'; '.join(result.failure_details[:3])}"
                )
                new_memory = existing + entry
                ws.safe_write(memory_path, new_memory[:5000])  # Cap memory file size
                logger.info("TesterAgent: Updated memory with failure patterns.")

        except Exception as e:
            logger.debug(f"TesterAgent memory update failed: {e}")
