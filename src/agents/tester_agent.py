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

    @property
    def pass_rate(self) -> float:
        total = self.passed + self.failed + self.errors
        return (self.passed / total * 100) if total > 0 else 0.0


class TesterAgent:
    """
    Independent agent that:
    1. Receives a diff/patch from the coder
    2. Generates targeted test cases for the changed code
    3. Runs them in the sandbox
    4. Reports results and updates its own memory file
    """

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

        Args:
            diff_text: The unified diff of code changes.
            language: Programming language of the project.
            test_command: Command to run tests.
            project_root: Root directory of the project.

        Returns:
            TestResult with pass/fail counts and generated test code.

        """
        result = TestResult()

        # 1. Generate test code using cheapest available model
        test_code = await self._generate_tests(diff_text, language)
        result.generated_test_code = test_code

        if not test_code:
            logger.warning("TesterAgent: No test code generated.")
            return result

        # 2. Run tests in sandbox
        try:
            from src.tools.sandbox import E2BSandbox
            sandbox = E2BSandbox()
            verification = await sandbox.run_test(
                test_command=test_command,
                project_root=project_root,
            )
            if verification and verification.test_result:
                result.passed = verification.test_result.tests_passed
                result.failed = verification.test_result.tests_failed
                result.failure_details = verification.test_result.test_failures or []
        except Exception as e:
            logger.error(f"TesterAgent sandbox execution failed: {e}")
            result.errors = 1
            result.failure_details.append(str(e))

        # 3. Update tester memory
        await self._update_memory(diff_text, result)

        return result

    async def _generate_tests(self, diff_text: str, language: str) -> str:
        """Use cheapest model to generate targeted tests for the diff."""
        try:
            available = self.registry.get_available_models()
            if not available:
                logger.warning("TesterAgent: No API keys configured — cannot generate tests.")
                return ""

            cheapest = sorted(available, key=lambda x: x.input_cost_per_mtok)[0]

            from src.agents.factory import PROVIDER_KEY_MAP, AgentFactory
            from src.auth.keychain import KeyChainManager

            key_name = PROVIDER_KEY_MAP.get(cheapest.provider.value)
            api_key = KeyChainManager.get_key(key_name) if key_name else None
            if not api_key:
                return ""

            agent = AgentFactory.create_agent(cheapest, api_key=api_key)
            agent.config.max_tokens = self.MAX_TEST_GEN_TOKENS

            system_prompt = (
                f"You are a senior test engineer. Given a code diff in {language}, "
                "generate focused unit tests that cover the changed lines. "
                "Output ONLY the test code. No explanations."
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"DIFF:\n{diff_text[:3000]}"},
            ]

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
