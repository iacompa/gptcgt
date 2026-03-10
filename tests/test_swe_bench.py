"""Tests for Phase 4 — Private SWE-bench."""

import json

import pytest

from src.core.swe_bench import (
    BenchmarkDataset,
    BenchmarkRunner,
    BenchmarkScorer,
    BenchmarkTask,
    Difficulty,
    RunResult,
    TaskCategory,
)

# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def simple_task() -> BenchmarkTask:
    return BenchmarkTask(
        task_id="test-001",
        title="Add function",
        description="Write a function `add(a, b)` that returns a + b.",
        difficulty=Difficulty.EASY,
        category=TaskCategory.BUG_FIX,
        hidden_test_code="assert add(1, 2) == 3\nassert add(-1, 1) == 0\nassert add(0, 0) == 0",
        expected_files=["math_utils.py"],
        forbidden_patterns=["__import__", "os.system"],
    )


@pytest.fixture
def sample_tasks() -> list[BenchmarkTask]:
    return [
        BenchmarkTask(
            task_id="bench-001",
            title="Fix divide by zero",
            description="Fix the divide function to handle zero divisor.",
            difficulty=Difficulty.EASY,
            category=TaskCategory.BUG_FIX,
            hidden_test_code="assert safe_divide(10, 2) == 5\nassert safe_divide(10, 0) == 0",
        ),
        BenchmarkTask(
            task_id="bench-002",
            title="Add caching",
            description="Add LRU cache to the compute function.",
            difficulty=Difficulty.MEDIUM,
            category=TaskCategory.FEATURE,
            hidden_test_code="assert compute(5) == 25",
        ),
        BenchmarkTask(
            task_id="bench-003",
            title="Sanitize input",
            description="Sanitize user input to prevent injection.",
            difficulty=Difficulty.HARD,
            category=TaskCategory.SECURITY,
            hidden_test_code='assert sanitize("<script>bad</script>") == "bad"',
        ),
    ]


# ── BenchmarkTask Tests ────────────────────────────────────────────────

class TestBenchmarkTask:

    def test_to_dict_excludes_hidden(self, simple_task):
        d = simple_task.to_dict()
        assert "hidden_test_code" not in d
        assert "forbidden_patterns" not in d
        assert d["task_id"] == "test-001"

    def test_to_agent_prompt(self, simple_task):
        prompt = simple_task.to_agent_prompt()
        assert "Add function" in prompt
        assert "add(a, b)" in prompt
        assert "hidden" not in prompt.lower()
        assert "assert" not in prompt  # No test leakage

    def test_difficulty_enum(self):
        assert Difficulty.EASY.value == "easy"
        assert Difficulty.EXPERT.value == "expert"

    def test_category_enum(self):
        assert TaskCategory.BUG_FIX.value == "bug_fix"
        assert TaskCategory.SECURITY.value == "security"


# ── BenchmarkDataset Tests ──────────────────────────────────────────────

class TestBenchmarkDataset:

    def test_load_from_directory(self, tmp_path, simple_task):
        bench_dir = tmp_path / "benchmark"
        bench_dir.mkdir()
        from dataclasses import asdict
        (bench_dir / "test-001.json").write_text(json.dumps(asdict(simple_task), indent=2))

        ds = BenchmarkDataset(bench_dir)
        tasks = ds.load()
        assert len(tasks) == 1
        assert tasks[0].task_id == "test-001"

    def test_load_empty_directory(self, tmp_path):
        bench_dir = tmp_path / "benchmark"
        bench_dir.mkdir()
        ds = BenchmarkDataset(bench_dir)
        tasks = ds.load()
        assert len(tasks) == 0

    def test_load_missing_directory(self, tmp_path):
        ds = BenchmarkDataset(tmp_path / "nonexistent")
        tasks = ds.load()
        assert len(tasks) == 0

    def test_get_by_id(self, tmp_path, simple_task):
        bench_dir = tmp_path / "benchmark"
        bench_dir.mkdir()
        from dataclasses import asdict
        (bench_dir / "test-001.json").write_text(json.dumps(asdict(simple_task)))

        ds = BenchmarkDataset(bench_dir)
        ds.load()
        assert ds.get_by_id("test-001") is not None
        assert ds.get_by_id("nonexistent") is None

    def test_get_by_category(self, sample_tasks):
        ds = BenchmarkDataset()
        ds.tasks = sample_tasks
        bug_fixes = ds.get_by_category(TaskCategory.BUG_FIX)
        assert len(bug_fixes) == 1
        assert bug_fixes[0].task_id == "bench-001"

    def test_get_by_difficulty(self, sample_tasks):
        ds = BenchmarkDataset()
        ds.tasks = sample_tasks
        easy = ds.get_by_difficulty(Difficulty.EASY)
        assert len(easy) == 1
        hard = ds.get_by_difficulty(Difficulty.HARD)
        assert len(hard) == 1

    def test_add_task_persists(self, tmp_path, simple_task):
        ds = BenchmarkDataset(tmp_path / "benchmark")
        ds.add_task(simple_task)
        assert (tmp_path / "benchmark" / "test-001.json").exists()
        assert len(ds.tasks) == 1


# ── BenchmarkRunner Tests ──────────────────────────────────────────────

class TestBenchmarkRunner:

    @pytest.mark.asyncio
    async def test_passing_solution(self, simple_task):
        runner = BenchmarkRunner()
        solution = "def add(a, b):\n    return a + b"
        result = await runner.run_task(simple_task, solution, tokens_used=500, cost_usd=0.01)
        assert result.passed
        assert result.tests_passed == 3
        assert result.tests_failed == 0
        assert result.tokens_used == 500

    @pytest.mark.asyncio
    async def test_failing_solution(self, simple_task):
        runner = BenchmarkRunner()
        solution = "def add(a, b):\n    return 42"  # Always returns 42
        result = await runner.run_task(simple_task, solution)
        assert not result.passed
        assert result.tests_failed > 0

    @pytest.mark.asyncio
    async def test_anti_gaming_forbidden_pattern(self, simple_task):
        runner = BenchmarkRunner()
        solution = "import os\nos.system('echo hack')\ndef add(a, b):\n    return a + b"
        result = await runner.run_task(simple_task, solution)
        assert not result.passed
        assert len(result.anti_gaming_flags) > 0
        assert "Forbidden pattern" in result.anti_gaming_flags[0]

    @pytest.mark.asyncio
    async def test_anti_gaming_trivial_solution(self, simple_task):
        runner = BenchmarkRunner()
        solution = "pass"  # Too trivial
        result = await runner.run_task(simple_task, solution)
        assert not result.passed
        assert any("trivial" in f.lower() for f in result.anti_gaming_flags)

    @pytest.mark.asyncio
    async def test_empty_hidden_tests(self):
        task = BenchmarkTask(task_id="no-tests", title="No tests", description="Task with no hidden tests")
        runner = BenchmarkRunner()
        result = await runner.run_task(task, "pass")
        # No anti-gaming flag for trivial since hidden_test_code is empty —
        # but trivial solution flag should still fire
        assert not result.passed or result.tests_total == 0

    @pytest.mark.asyncio
    async def test_latency_tracking(self, simple_task):
        runner = BenchmarkRunner()
        solution = "def add(a, b):\n    return a + b"
        result = await runner.run_task(simple_task, solution)
        assert result.latency_seconds >= 0


# ── BenchmarkScorer Tests ──────────────────────────────────────────────

class TestBenchmarkScorer:

    def test_perfect_score(self):
        results = [
            RunResult(task_id="t1", passed=True, tokens_used=500, cost_usd=0.01),
            RunResult(task_id="t2", passed=True, tokens_used=800, cost_usd=0.02),
        ]
        scorer = BenchmarkScorer()
        score = scorer.score(results)
        assert score.correctness == 100.0
        assert score.robustness == 100.0
        assert score.overall >= 90.0
        assert score.grade in ("A+", "A")

    def test_zero_score(self):
        results = [
            RunResult(task_id="t1", passed=False, tokens_used=5000),
            RunResult(task_id="t2", passed=False, tokens_used=5000),
        ]
        scorer = BenchmarkScorer()
        score = scorer.score(results)
        assert score.correctness == 0.0
        assert score.grade == "F"

    def test_anti_gaming_penalty(self):
        results = [
            RunResult(task_id="t1", passed=True, tokens_used=500, anti_gaming_flags=["suspicious"]),
            RunResult(task_id="t2", passed=True, tokens_used=500),
        ]
        scorer = BenchmarkScorer()
        score = scorer.score(results)
        assert score.robustness < 100.0  # Penalized

    def test_efficiency_scaling(self):
        # Low tokens = high efficiency
        low_token = [RunResult(task_id="t1", passed=True, tokens_used=500)]
        high_token = [RunResult(task_id="t2", passed=True, tokens_used=15000)]

        scorer = BenchmarkScorer()
        low_score = scorer.score(low_token)
        high_score = scorer.score(high_token)
        assert low_score.efficiency > high_score.efficiency

    def test_empty_results(self):
        scorer = BenchmarkScorer()
        score = scorer.score([])
        assert score.tasks_attempted == 0
        assert score.overall == 0.0

    def test_format_report(self):
        results = [RunResult(task_id="t1", passed=True, tokens_used=1000, cost_usd=0.01)]
        scorer = BenchmarkScorer()
        score = scorer.score(results)
        report = scorer.format_report(score)
        assert "SWE-bench Results" in report
        assert "Correctness" in report
        assert "Robustness" in report

    def test_grade_assignment(self):
        scorer = BenchmarkScorer()
        # All passing with low tokens should be A+
        results = [RunResult(task_id=f"t{i}", passed=True, tokens_used=500) for i in range(5)]
        score = scorer.score(results)
        assert score.grade in ("A+", "A")
