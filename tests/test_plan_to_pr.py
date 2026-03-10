"""Tests for Phase 2 — Plan-to-PR Guided Build Mode."""

import json

import pytest

from src.core.plan_to_pr import (
    DecisionsLog,
    DecisionStatus,
    Intent,
    IntentDetector,
    PlanArtifactPack,
    PlanInterviewEngine,
)

# ── IntentDetector Tests ────────────────────────────────────────────────

class TestIntentDetector:
    """Test first-turn intent classification."""

    def test_short_input_is_direct(self):
        assert IntentDetector.classify("fix the bug") == Intent.DIRECT

    def test_build_keyword_triggers_plan(self):
        result = IntentDetector.classify(
            "I want to build a complete authentication system with OAuth2 and RBAC "
            "that integrates with our existing user model across multiple files"
        )
        assert result == Intent.PLAN

    def test_fix_keyword_triggers_direct(self):
        assert IntentDetector.classify("fix this crash in the login handler") == Intent.DIRECT

    def test_long_input_without_keywords_is_plan(self):
        long_input = (
            "I need a system that handles user registration, email verification, "
            "password reset flows, session management, and integrates with our "
            "existing PostgreSQL database. It should also support team invitations "
            "and role-based access control with admin and member tiers."
        )
        assert IntentDetector.classify(long_input) == Intent.PLAN

    def test_explicit_plan_first_phrase(self):
        result = IntentDetector.classify(
            "Let's plan first before coding. I want to create a new billing module."
        )
        assert result == Intent.PLAN

    def test_simple_question_is_direct(self):
        assert IntentDetector.classify("what is the purpose of this function") == Intent.DIRECT

    def test_multi_file_scope_is_plan(self):
        result = IntentDetector.classify(
            "refactor the payment system across multiple files to support subscriptions"
        )
        assert result == Intent.PLAN


# ── DecisionsLog Tests ──────────────────────────────────────────────────

class TestDecisionsLog:
    """Test decision tracking state machine."""

    def test_add_decision(self):
        log = DecisionsLog()
        idx = log.add("What framework?", category="tech_stack")
        assert idx == 0
        assert len(log.decisions) == 1
        assert log.decisions[0].status == DecisionStatus.OPEN

    def test_resolve_decision(self):
        log = DecisionsLog()
        idx = log.add("What database?")
        log.resolve(idx, "PostgreSQL", rationale="Team expertise")
        assert log.decisions[idx].status == DecisionStatus.RESOLVED
        assert log.decisions[idx].answer == "PostgreSQL"
        assert log.decisions[idx].rationale == "Team expertise"

    def test_defer_decision(self):
        log = DecisionsLog()
        idx = log.add("Deployment strategy?", category="deployment")
        log.defer(idx, "Will decide after MVP")
        assert log.decisions[idx].status == DecisionStatus.DEFERRED

    def test_open_decisions_tracking(self):
        log = DecisionsLog()
        log.add("Q1")
        log.add("Q2")
        idx3 = log.add("Q3")
        log.resolve(idx3, "Answer 3")
        open_ones = log.open_decisions
        assert len(open_ones) == 2

    def test_is_complete(self):
        log = DecisionsLog()
        idx1 = log.add("Q1")
        idx2 = log.add("Q2")
        assert not log.is_complete
        log.resolve(idx1, "A1")
        assert not log.is_complete
        log.resolve(idx2, "A2")
        assert log.is_complete

    def test_to_markdown_output(self):
        log = DecisionsLog()
        idx = log.add("What framework?", category="tech_stack")
        log.resolve(idx, "FastAPI", rationale="Async support")
        md = log.to_markdown()
        assert "# Decisions Log" in md
        assert "Resolved (1)" in md
        assert "FastAPI" in md
        assert "Async support" in md

    def test_resolved_decisions_property(self):
        log = DecisionsLog()
        idx1 = log.add("Q1")
        log.add("Q2")
        log.resolve(idx1, "A1")
        resolved = log.resolved_decisions
        assert len(resolved) == 1
        assert resolved[0].answer == "A1"


# ── PlanInterviewEngine Tests ──────────────────────────────────────────

class TestPlanInterviewEngine:
    """Test adaptive interview flow."""

    def test_first_question_is_scope(self):
        engine = PlanInterviewEngine()
        q = engine.get_next_question()
        assert q is not None
        assert "goal" in q.lower() or "primary" in q.lower()

    def test_progress_tracking(self):
        engine = PlanInterviewEngine()
        progress = engine.get_progress()
        assert progress["questions_asked"] == 0
        assert not progress["is_complete"]

    def test_answer_advances_state(self):
        engine = PlanInterviewEngine()
        q = engine.get_next_question()
        assert q is not None
        engine.record_answer(q, "Build a task management system")
        progress = engine.get_progress()
        assert progress["questions_asked"] == 1

    def test_skip_category_advances(self):
        engine = PlanInterviewEngine()
        engine.skip_category("security")
        engine.skip_category("deployment")
        progress = engine.get_progress()
        assert "security" not in progress["categories_remaining"]
        assert "deployment" not in progress["categories_remaining"]

    def test_interview_completes_after_scope_and_arch(self):
        engine = PlanInterviewEngine(max_questions=20)

        # Answer all scope questions
        while True:
            q = engine.get_next_question()
            if q is None or engine._categorize_question(q) != "scope":
                break
            engine.record_answer(q, "Test answer for scope")

        # Answer all arch questions
        while True:
            q = engine.get_next_question()
            if q is None or engine._categorize_question(q) != "arch":
                break
            engine.record_answer(q, "Test answer for arch")

        # Should be complete (>= min_questions and scope+arch done)
        assert engine.is_complete or engine.state.total_asked >= engine.state.min_questions

    def test_skip_answer_skips_category(self):
        engine = PlanInterviewEngine()
        q = engine.get_next_question()
        assert q is not None
        engine.record_answer(q, "skip")
        # "skip" should mark the category as done
        assert engine._categorize_question(q) in engine.state.categories_completed

    def test_max_questions_limit(self):
        engine = PlanInterviewEngine(max_questions=3)
        for _ in range(3):
            q = engine.get_next_question()
            if q:
                engine.record_answer(q, "answer")
        assert engine.is_complete

    def test_decisions_populated(self):
        engine = PlanInterviewEngine()
        q = engine.get_next_question()
        assert q is not None
        engine.record_answer(q, "My project goal")
        assert len(engine.decisions.decisions) == 1
        assert engine.decisions.decisions[0].answer == "My project goal"


# ── PlanArtifactPack Tests ──────────────────────────────────────────────

class TestPlanArtifactPack:
    """Test plan artifact generation."""

    @pytest.fixture
    def populated_decisions(self):
        log = DecisionsLog()
        idx1 = log.add("What is the goal?", category="scope")
        log.resolve(idx1, "Build a task management API")
        idx2 = log.add("Database choice?", category="arch")
        log.resolve(idx2, "PostgreSQL")
        idx3 = log.add("Auth model?", category="security")
        log.resolve(idx3, "JWT with refresh tokens")
        idx4 = log.add("Min test coverage?", category="testing")
        log.resolve(idx4, "80% line coverage")
        idx5 = log.add("Rollout strategy?", category="deployment")
        log.resolve(idx5, "Gradual with feature flags")
        return log

    def test_generate_all_creates_files(self, populated_decisions, tmp_path):
        pack = PlanArtifactPack(populated_decisions, goal="Task Management API")
        artifacts = pack.generate_all(tmp_path / "plan")
        assert len(artifacts) == 6
        assert (tmp_path / "plan" / "project_plan.md").exists()
        assert (tmp_path / "plan" / "decisions_log.md").exists()
        assert (tmp_path / "plan" / "task_graph.json").exists()
        assert (tmp_path / "plan" / "risk_register.md").exists()
        assert (tmp_path / "plan" / "acceptance_criteria.md").exists()
        assert (tmp_path / "plan" / "rollout_and_rollback.md").exists()

    def test_project_plan_contains_scope(self, populated_decisions, tmp_path):
        pack = PlanArtifactPack(populated_decisions, goal="Task Management API")
        artifacts = pack.generate_all(tmp_path / "plan")
        plan = artifacts["project_plan.md"]
        assert "Task Management API" in plan
        assert "## Scope" in plan
        assert "task management api" in plan.lower()

    def test_task_graph_is_valid_json(self, populated_decisions, tmp_path):
        pack = PlanArtifactPack(populated_decisions, goal="Task Management API")
        artifacts = pack.generate_all(tmp_path / "plan")
        graph = json.loads(artifacts["task_graph.json"])
        assert "tasks" in graph
        assert "total_tasks" in graph
        assert graph["total_tasks"] > 0
        # Verify DAG structure: tasks have depends_on
        for task in graph["tasks"]:
            assert "id" in task
            assert "depends_on" in task
            assert "status" in task

    def test_risk_register_format(self, populated_decisions, tmp_path):
        pack = PlanArtifactPack(populated_decisions, goal="Task Management API")
        artifacts = pack.generate_all(tmp_path / "plan")
        risks = artifacts["risk_register.md"]
        assert "# Risk Register" in risks
        assert "Likelihood" in risks
        assert "Mitigation" in risks

    def test_acceptance_criteria_includes_nonfunctional(self, populated_decisions, tmp_path):
        pack = PlanArtifactPack(populated_decisions, goal="Task Management API")
        artifacts = pack.generate_all(tmp_path / "plan")
        criteria = artifacts["acceptance_criteria.md"]
        assert "NF-1" in criteria
        assert "zero failures" in criteria.lower() or "All tests pass" in criteria

    def test_rollout_plan_has_rollback(self, populated_decisions, tmp_path):
        pack = PlanArtifactPack(populated_decisions, goal="Task Management API")
        artifacts = pack.generate_all(tmp_path / "plan")
        rollout = artifacts["rollout_and_rollback.md"]
        assert "Rollback" in rollout
        assert "Revert" in rollout or "revert" in rollout

    def test_empty_decisions_still_generates(self, tmp_path):
        empty_log = DecisionsLog()
        pack = PlanArtifactPack(empty_log, goal="Minimal Project")
        artifacts = pack.generate_all(tmp_path / "plan")
        assert len(artifacts) == 6
        # All files should exist even with no decisions
        for name in artifacts:
            assert (tmp_path / "plan" / name).exists()
