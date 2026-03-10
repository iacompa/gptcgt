"""
Phase 4 — Private SWE-bench.

A private benchmark system that evaluates autonomous agent solutions
against a curated set of tasks. Prevents gaming and provides
multi-dimensional scoring.

Components:
  1. BenchmarkTask — task definition with hidden acceptance tests
  2. BenchmarkDataset — loads/manages tasks from .gptcgt/benchmark/
  3. BenchmarkRunner — executes solutions in isolated environments
  4. BenchmarkScorer — multi-metric scoring with anti-gaming checks

Anti-gaming measures:
  - Hidden test code never exposed to the agent
  - Penalize hardcoded/magic values
  - Cross-task consistency checks
  - Reject solutions that leak test expectations
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger("core.swe_bench")


# ── Task Definition ─────────────────────────────────────────────────────

class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class TaskCategory(str, Enum):
    BUG_FIX = "bug_fix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    SECURITY = "security"
    PERFORMANCE = "performance"
    TEST_ADDITION = "test_addition"


@dataclass
class BenchmarkTask:
    """A single benchmark task definition."""

    task_id: str
    title: str
    description: str  # What the agent sees
    difficulty: Difficulty = Difficulty.MEDIUM
    category: TaskCategory = TaskCategory.BUG_FIX
    language: str = "python"

    # Hidden from the agent
    hidden_test_code: str = ""  # Acceptance test that validates the solution
    expected_files: list[str] = field(default_factory=list)  # Files that should be modified
    forbidden_patterns: list[str] = field(default_factory=list)  # Patterns that indicate gaming

    # Metadata
    max_tokens: int = 10000
    time_limit_seconds: int = 300
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dict (excludes hidden test code for agent exposure)."""
        d = asdict(self)
        d.pop("hidden_test_code", None)
        d.pop("forbidden_patterns", None)
        return d

    def to_agent_prompt(self) -> str:
        """Generate the prompt the agent sees (no hidden info)."""
        return (
            f"## Task: {self.title}\n\n"
            f"**Difficulty:** {self.difficulty.value}\n"
            f"**Category:** {self.category.value}\n"
            f"**Language:** {self.language}\n\n"
            f"### Description\n\n{self.description}\n\n"
            f"### Expected Files\n\n"
            + "\n".join(f"- `{f}`" for f in self.expected_files)
        )


# ── Benchmark Dataset ───────────────────────────────────────────────────

class BenchmarkDataset:
    """Load and manage benchmark tasks from a directory."""

    def __init__(self, benchmark_dir: Path | None = None) -> None:
        self.benchmark_dir = benchmark_dir or Path(".gptcgt/benchmark")
        self.tasks: list[BenchmarkTask] = []

    def load(self) -> list[BenchmarkTask]:
        """Load all tasks from the benchmark directory."""
        self.tasks = []

        if not self.benchmark_dir.exists():
            logger.warning(f"Benchmark directory not found: {self.benchmark_dir}")
            return self.tasks

        for task_file in sorted(self.benchmark_dir.glob("*.json")):
            try:
                data = json.loads(task_file.read_text())
                task = self._parse_task(data)
                self.tasks.append(task)
            except Exception as e:
                logger.warning(f"Failed to load benchmark task {task_file}: {e}")

        logger.info(f"Loaded {len(self.tasks)} benchmark tasks")
        return self.tasks

    def get_by_id(self, task_id: str) -> BenchmarkTask | None:
        """Get a task by its ID."""
        return next((t for t in self.tasks if t.task_id == task_id), None)

    def get_by_category(self, category: TaskCategory) -> list[BenchmarkTask]:
        """Get all tasks of a specific category."""
        return [t for t in self.tasks if t.category == category]

    def get_by_difficulty(self, difficulty: Difficulty) -> list[BenchmarkTask]:
        """Get all tasks of a specific difficulty."""
        return [t for t in self.tasks if t.difficulty == difficulty]

    def add_task(self, task: BenchmarkTask) -> None:
        """Add a task to the dataset (and persist to disk)."""
        self.tasks.append(task)
        self.benchmark_dir.mkdir(parents=True, exist_ok=True)
        task_path = self.benchmark_dir / f"{task.task_id}.json"
        task_data = asdict(task)
        task_path.write_text(json.dumps(task_data, indent=2))

    @staticmethod
    def _parse_task(data: dict) -> BenchmarkTask:
        """Parse a task from JSON data."""
        return BenchmarkTask(
            task_id=data["task_id"],
            title=data["title"],
            description=data["description"],
            difficulty=Difficulty(data.get("difficulty", "medium")),
            category=TaskCategory(data.get("category", "bug_fix")),
            language=data.get("language", "python"),
            hidden_test_code=data.get("hidden_test_code", ""),
            expected_files=data.get("expected_files", []),
            forbidden_patterns=data.get("forbidden_patterns", []),
            max_tokens=data.get("max_tokens", 10000),
            time_limit_seconds=data.get("time_limit_seconds", 300),
            tags=data.get("tags", []),
        )


# ── Benchmark Runner ────────────────────────────────────────────────────

@dataclass
class RunResult:
    """Result of running a solution against a benchmark task."""

    task_id: str
    passed: bool = False
    tests_passed: int = 0
    tests_failed: int = 0
    tests_total: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0
    latency_seconds: float = 0.0
    solution_code: str = ""
    error: str = ""
    anti_gaming_flags: list[str] = field(default_factory=list)


class BenchmarkRunner:
    """Execute solutions against benchmark tasks."""

    def __init__(self) -> None:
        self.results: list[RunResult] = []

    async def run_task(
        self,
        task: BenchmarkTask,
        solution_code: str,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
    ) -> RunResult:
        """Run a solution against a task's hidden tests."""
        start = time.monotonic()

        result = RunResult(
            task_id=task.task_id,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            solution_code=solution_code,
        )

        # 1. Anti-gaming check
        gaming_flags = self._check_anti_gaming(task, solution_code)
        result.anti_gaming_flags = gaming_flags

        if gaming_flags:
            result.passed = False
            result.error = f"Anti-gaming flags: {'; '.join(gaming_flags)}"
            result.latency_seconds = time.monotonic() - start
            self.results.append(result)
            return result

        # 2. Execute hidden tests
        try:
            test_result = await self._execute_tests(task, solution_code)
            result.tests_passed = test_result["passed"]
            result.tests_failed = test_result["failed"]
            result.tests_total = test_result["total"]
            result.passed = test_result["failed"] == 0 and test_result["total"] > 0
        except Exception as e:
            result.error = str(e)
            result.passed = False

        result.latency_seconds = time.monotonic() - start
        self.results.append(result)
        return result

    def _check_anti_gaming(self, task: BenchmarkTask, solution: str) -> list[str]:
        """Check for common gaming patterns."""
        flags = []

        # Check forbidden patterns
        for pattern in task.forbidden_patterns:
            if pattern in solution:
                flags.append(f"Forbidden pattern detected: '{pattern[:30]}'")

        # Check for hardcoded test expectations
        hardcode_patterns = [
            r"assert\s+\w+\s*==\s*['\"].*['\"]",  # Hardcoded string assertions
            r"return\s+['\"].*['\"]",  # Hardcoded return values (suspicious)
        ]
        for pat in hardcode_patterns:
            matches = re.findall(pat, solution)
            if len(matches) > 5:  # More than 5 hardcoded values is suspicious
                flags.append(f"Excessive hardcoded values detected ({len(matches)} matches)")

        # Check for test code leakage (solution contains test expectations)
        if task.hidden_test_code:
            # Extract assertion values from hidden tests
            test_values = re.findall(r'assert.*==\s*(["\'].*?["\']|\d+)', task.hidden_test_code)
            leaked = [v for v in test_values if v in solution]
            if len(leaked) > 3:
                flags.append(f"Possible test leakage: {len(leaked)} test values found in solution")

        # Check for empty/trivial solutions
        lines = [line.strip() for line in solution.splitlines() if line.strip() and not line.strip().startswith("#")]
        if len(lines) < 2:
            flags.append("Solution too trivial (< 2 meaningful lines)")

        return flags

    async def _execute_tests(self, task: BenchmarkTask, solution: str) -> dict:
        """Execute the hidden test code against the solution."""
        # In production, this would use E2B sandbox
        # For now, we do a safe local execution with exec()
        test_code = task.hidden_test_code
        if not test_code:
            return {"passed": 0, "failed": 0, "total": 0}

        # Build a combined execution context
        namespace: dict = {}
        passed = 0
        failed = 0
        total = 0

        try:
            # Execute solution to define functions/classes
            exec(solution, namespace)  # noqa: S102

            # Execute each test assertion
            for line in test_code.splitlines():
                line = line.strip()
                if line.startswith("assert ") or line.startswith("assert("):
                    total += 1
                    try:
                        exec(line, namespace)  # noqa: S102
                        passed += 1
                    except AssertionError:
                        failed += 1
                    except Exception:
                        failed += 1

        except Exception as e:
            logger.warning(f"Test execution failed: {e}")
            return {"passed": 0, "failed": 1, "total": 1}

        return {"passed": passed, "failed": failed, "total": total}


# ── Benchmark Scorer ────────────────────────────────────────────────────

@dataclass
class BenchmarkScore:
    """Multi-dimensional benchmark score."""

    # Core metrics (0-100)
    correctness: float = 0.0
    robustness: float = 0.0
    efficiency: float = 0.0
    consistency: float = 0.0

    # Computed
    overall: float = 0.0
    grade: str = "F"

    # Details
    tasks_attempted: int = 0
    tasks_passed: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    anti_gaming_violations: int = 0

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return asdict(self)


class BenchmarkScorer:
    """Score benchmark results across multiple dimensions."""

    # Weights for overall score
    WEIGHTS = {
        "correctness": 0.40,
        "robustness": 0.25,
        "efficiency": 0.20,
        "consistency": 0.15,
    }

    # Grade thresholds
    GRADES = [
        (90, "A+"), (85, "A"), (80, "A-"),
        (75, "B+"), (70, "B"), (65, "B-"),
        (60, "C+"), (55, "C"), (50, "C-"),
        (40, "D"), (0, "F"),
    ]

    def score(self, results: list[RunResult], tasks: list[BenchmarkTask] | None = None) -> BenchmarkScore:
        """Compute multi-dimensional score from run results."""
        score = BenchmarkScore()

        if not results:
            return score

        score.tasks_attempted = len(results)
        score.tasks_passed = sum(1 for r in results if r.passed)
        score.total_tokens = sum(r.tokens_used for r in results)
        score.total_cost_usd = sum(r.cost_usd for r in results)
        score.anti_gaming_violations = sum(1 for r in results if r.anti_gaming_flags)

        # 1. Correctness: % of tasks passed
        score.correctness = (score.tasks_passed / score.tasks_attempted) * 100

        # 2. Robustness: penalize for anti-gaming violations
        if score.anti_gaming_violations > 0:
            penalty = min(50, score.anti_gaming_violations * 15)
            score.robustness = max(0, 100 - penalty)
        else:
            score.robustness = 100.0

        # 3. Efficiency: reward lower token usage per passing task
        passing_results = [r for r in results if r.passed]
        if passing_results:
            avg_tokens = sum(r.tokens_used for r in passing_results) / len(passing_results)
            # Scale: 1000 tokens = 100%, 10000 = 50%, 20000+ = 10%
            if avg_tokens <= 1000:
                score.efficiency = 100.0
            elif avg_tokens <= 10000:
                score.efficiency = 100 - (avg_tokens - 1000) / 9000 * 50
            else:
                score.efficiency = max(10.0, 50 - (avg_tokens - 10000) / 10000 * 40)
        else:
            score.efficiency = 0.0

        # 4. Consistency: reward even performance across categories
        if tasks and len(results) > 1:
            categories = set(t.category for t in tasks)
            category_scores = []
            for cat in categories:
                cat_results = [r for r, t in zip(results, tasks) if t.category == cat]
                if cat_results:
                    cat_pass_rate = sum(1 for r in cat_results if r.passed) / len(cat_results)
                    category_scores.append(cat_pass_rate)
            if category_scores and len(category_scores) > 1:
                mean = sum(category_scores) / len(category_scores)
                variance = sum((s - mean) ** 2 for s in category_scores) / len(category_scores)
                # Low variance = high consistency
                score.consistency = max(0, 100 * (1 - variance * 2))
            else:
                score.consistency = score.correctness
        else:
            score.consistency = score.correctness

        # Overall weighted score
        score.overall = (
            score.correctness * self.WEIGHTS["correctness"]
            + score.robustness * self.WEIGHTS["robustness"]
            + score.efficiency * self.WEIGHTS["efficiency"]
            + score.consistency * self.WEIGHTS["consistency"]
        )

        # Assign grade
        for threshold, grade in self.GRADES:
            if score.overall >= threshold:
                score.grade = grade
                break

        return score

    def format_report(self, score: BenchmarkScore) -> str:
        """Format score as a readable report."""
        lines = [
            "# SWE-bench Results\n",
            f"**Overall Score:** {score.overall:.1f}/100 ({score.grade})\n",
            "## Dimension Scores\n",
            "| Dimension | Score | Weight |",
            "|-----------|-------|--------|",
            f"| Correctness | {score.correctness:.1f} | {self.WEIGHTS['correctness']:.0%} |",
            f"| Robustness | {score.robustness:.1f} | {self.WEIGHTS['robustness']:.0%} |",
            f"| Efficiency | {score.efficiency:.1f} | {self.WEIGHTS['efficiency']:.0%} |",
            f"| Consistency | {score.consistency:.1f} | {self.WEIGHTS['consistency']:.0%} |",
            "",
            "## Statistics\n",
            f"- Tasks attempted: {score.tasks_attempted}",
            f"- Tasks passed: {score.tasks_passed}",
            f"- Total tokens: {score.total_tokens:,}",
            f"- Total cost: ${score.total_cost_usd:.3f}",
            f"- Anti-gaming violations: {score.anti_gaming_violations}",
        ]
        return "\n".join(lines)
