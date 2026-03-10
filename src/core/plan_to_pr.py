"""
Phase 2 — Plan-to-PR Guided Build Mode.

Adaptive interview engine that converts vague project ideas into
structured, verifiable execution plans before any code is generated.

Three main components:
  1. IntentDetector — classifies first-turn input as PLAN or DIRECT
  2. PlanInterviewEngine — drives a 10-20 question adaptive interview
  3. PlanArtifactPack — generates all plan artifacts from decisions

Generated Artifacts:
  - .gptcgt/plan/project_plan.md
  - .gptcgt/plan/decisions_log.md
  - .gptcgt/plan/task_graph.json
  - .gptcgt/plan/risk_register.md
  - .gptcgt/plan/acceptance_criteria.md
  - .gptcgt/plan/rollout_and_rollback.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger("core.plan_to_pr")


# ── Intent Detection ────────────────────────────────────────────────────

class Intent(str, Enum):
    """First-turn intent classification."""

    PLAN = "plan"       # Complex build — needs interview
    DIRECT = "direct"   # Simple fix/question — skip interview


# Keywords that signal a complex build intent
_PLAN_KEYWORDS = frozenset({
    "build", "create", "design", "architect", "implement",
    "develop", "scaffold", "bootstrap", "set up", "migrate",
    "refactor", "rewrite", "overhaul", "rebuild", "revamp",
    "convert", "port", "integrate", "add feature", "new feature",
    "full stack", "fullstack", "end-to-end", "e2e",
})

# Keywords that signal a direct/simple intent
_DIRECT_KEYWORDS = frozenset({
    "fix", "bug", "error", "typo", "crash",
    "what is", "how to", "explain", "help",
    "rename", "move", "delete file", "remove",
    "update version", "bump", "quick",
})


class IntentDetector:
    """Classify first-turn user input as PLAN or DIRECT."""

    @staticmethod
    def classify(user_input: str) -> Intent:
        """Analyze user's first message to determine intent."""
        lower = user_input.lower().strip()
        word_count = len(lower.split())

        # Short messages (< 8 words) are usually direct requests
        if word_count < 8:
            return Intent.DIRECT

        # Check for explicit plan keywords
        plan_score = sum(1 for kw in _PLAN_KEYWORDS if kw in lower)
        direct_score = sum(1 for kw in _DIRECT_KEYWORDS if kw in lower)

        # Multi-file scope signals are strong plan indicators
        if any(phrase in lower for phrase in ("multiple files", "several components", "across the")):
            plan_score += 2

        # Explicit references to planning
        if any(phrase in lower for phrase in ("plan first", "before coding", "think through")):
            plan_score += 3

        if plan_score > direct_score:
            return Intent.PLAN

        # Long messages (> 30 words) with no direct keywords → likely a build
        if word_count > 30 and direct_score == 0:
            return Intent.PLAN

        return Intent.DIRECT


# ── Decisions Log ───────────────────────────────────────────────────────

class DecisionStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DEFERRED = "deferred"


@dataclass
class Decision:
    """A single architectural or implementation decision."""

    question: str
    answer: str = ""
    status: DecisionStatus = DecisionStatus.OPEN
    category: str = "general"  # arch, tech_stack, security, testing, deployment
    rationale: str = ""
    alternatives: list[str] = field(default_factory=list)


@dataclass
class DecisionsLog:
    """Ordered log of all decisions made during the interview."""

    decisions: list[Decision] = field(default_factory=list)
    _next_id: int = 0

    def add(self, question: str, category: str = "general") -> int:
        """Add a new open decision. Returns its index."""
        self.decisions.append(Decision(question=question, category=category))
        idx = self._next_id
        self._next_id += 1
        return idx

    def resolve(self, index: int, answer: str, rationale: str = "") -> None:
        """Resolve a decision with an answer."""
        if 0 <= index < len(self.decisions):
            self.decisions[index].answer = answer
            self.decisions[index].status = DecisionStatus.RESOLVED
            self.decisions[index].rationale = rationale

    def defer(self, index: int, reason: str = "") -> None:
        """Defer a decision for later."""
        if 0 <= index < len(self.decisions):
            self.decisions[index].status = DecisionStatus.DEFERRED
            self.decisions[index].rationale = reason or "Deferred to implementation phase"

    @property
    def open_decisions(self) -> list[tuple[int, Decision]]:
        """Return unresolved decisions with their indices."""
        return [(i, d) for i, d in enumerate(self.decisions) if d.status == DecisionStatus.OPEN]

    @property
    def resolved_decisions(self) -> list[Decision]:
        """Return all resolved decisions."""
        return [d for d in self.decisions if d.status == DecisionStatus.RESOLVED]

    @property
    def is_complete(self) -> bool:
        """True when no open decisions remain."""
        return not any(d.status == DecisionStatus.OPEN for d in self.decisions)

    def to_markdown(self) -> str:
        """Export decisions as a markdown document."""
        lines = ["# Decisions Log\n"]

        for status_label, status in [
            ("Resolved", DecisionStatus.RESOLVED),
            ("Deferred", DecisionStatus.DEFERRED),
            ("Open", DecisionStatus.OPEN),
        ]:
            group = [d for d in self.decisions if d.status == status]
            if group:
                lines.append(f"\n## {status_label} ({len(group)})\n")
                for d in group:
                    lines.append(f"### [{d.category}] {d.question}")
                    if d.answer:
                        lines.append(f"**Answer:** {d.answer}")
                    if d.rationale:
                        lines.append(f"**Rationale:** {d.rationale}")
                    if d.alternatives:
                        lines.append("**Alternatives considered:** " + ", ".join(d.alternatives))
                    lines.append("")

        return "\n".join(lines)


# ── Interview Engine ────────────────────────────────────────────────────

# Structured question templates organized by category
INTERVIEW_QUESTIONS: dict[str, list[str]] = {
    "scope": [
        "What is the primary goal of this project in one sentence?",
        "Who are the target users of this feature/system?",
        "What are the 3-5 must-have features for the initial version?",
        "What features should explicitly be out of scope for now?",
    ],
    "arch": [
        "Should this be a new standalone module or extend an existing one?",
        "What are the main data entities and their relationships?",
        "Do you need real-time features (WebSocket, SSE, polling)?",
        "Should this integrate with any external APIs or services?",
    ],
    "tech_stack": [
        "Any specific technology constraints or preferences?",
        "Should this follow the existing project patterns or introduce new ones?",
        "What database/storage approach fits best?",
    ],
    "security": [
        "What authentication/authorization model should be used?",
        "Are there any compliance requirements (GDPR, SOC2, etc.)?",
        "What data needs to be encrypted at rest or in transit?",
    ],
    "testing": [
        "What's the minimum acceptable test coverage?",
        "Should there be integration tests, or unit tests only?",
        "Are there specific edge cases that must be tested?",
    ],
    "deployment": [
        "What's the rollout strategy (gradual, feature flag, big bang)?",
        "What's the rollback plan if something goes wrong?",
        "Are there any performance or latency requirements?",
    ],
}


@dataclass
class InterviewState:
    """Tracks the progress of the interview."""

    phase: str = "scope"  # Current question category
    question_index: int = 0
    total_asked: int = 0
    max_questions: int = 20
    min_questions: int = 5
    categories_completed: list[str] = field(default_factory=list)
    _skip_categories: set[str] = field(default_factory=set)


class PlanInterviewEngine:
    """Adaptive interview engine that asks 5-20 targeted questions."""

    CATEGORY_ORDER = ["scope", "arch", "tech_stack", "security", "testing", "deployment"]

    def __init__(self, max_questions: int = 20) -> None:
        self.state = InterviewState(max_questions=max_questions)
        self.decisions = DecisionsLog()
        self._vision_summary: str = ""

    @property
    def is_complete(self) -> bool:
        """Interview is complete when enough questions asked and scope is clear."""
        if self.state.total_asked >= self.state.max_questions:
            return True
        if (
            self.state.total_asked >= self.state.min_questions
            and "scope" in self.state.categories_completed
            and "arch" in self.state.categories_completed
        ):
            return True
        return False

    def get_next_question(self) -> str | None:
        """Get the next question to ask, or None if interview is complete."""
        if self.is_complete:
            return None

        # Find current category questions
        for category in self.CATEGORY_ORDER:
            if category in self.state.categories_completed:
                continue
            if category in self.state._skip_categories:
                continue

            questions = INTERVIEW_QUESTIONS.get(category, [])
            # Find first unanswered question in this category
            answered_in_cat = sum(
                1 for d in self.decisions.decisions if d.category == category
            )
            if answered_in_cat < len(questions):
                question = questions[answered_in_cat]
                return question

            # All questions in category answered
            self.state.categories_completed.append(category)

        return None

    def record_answer(self, question: str, answer: str) -> None:
        """Record an answer and advance the interview state."""
        # Determine category
        category = self._categorize_question(question)
        idx = self.decisions.add(question, category=category)
        self.decisions.resolve(idx, answer)
        self.state.total_asked += 1

        # Adaptive skipping: if user says "default" or "skip", mark minimal
        lower_answer = answer.lower().strip()
        if lower_answer in ("skip", "default", "n/a", "whatever you think"):
            # Skip remaining questions in this category
            self.state._skip_categories.add(category)
            self.state.categories_completed.append(category)

        # Track vision delta for convergence detection
        self._update_vision_summary(question, answer)

    def skip_category(self, category: str) -> None:
        """Skip all remaining questions in a category."""
        self.state._skip_categories.add(category)
        if category not in self.state.categories_completed:
            self.state.categories_completed.append(category)

    def get_progress(self) -> dict:
        """Return interview progress metrics."""
        return {
            "questions_asked": self.state.total_asked,
            "max_questions": self.state.max_questions,
            "categories_completed": self.state.categories_completed,
            "categories_remaining": [
                c for c in self.CATEGORY_ORDER
                if c not in self.state.categories_completed
                and c not in self.state._skip_categories
            ],
            "is_complete": self.is_complete,
        }

    def _categorize_question(self, question: str) -> str:
        """Map a question back to its category."""
        for category, questions in INTERVIEW_QUESTIONS.items():
            if question in questions:
                return category
        return "general"

    def _update_vision_summary(self, question: str, answer: str) -> None:
        """Build a running summary of the project vision."""
        self._vision_summary += f"\n- {question}: {answer}"


# ── Plan Artifact Pack ──────────────────────────────────────────────────

class PlanArtifactPack:
    """Generate all plan artifacts from interview decisions."""

    def __init__(self, decisions: DecisionsLog, goal: str = "") -> None:
        self.decisions = decisions
        self.goal = goal

    def generate_all(self, output_dir: Path) -> dict[str, str]:
        """Generate all plan artifacts and write to output_dir."""
        output_dir.mkdir(parents=True, exist_ok=True)
        artifacts = {}

        # 1. Project Plan
        plan = self._generate_project_plan()
        (output_dir / "project_plan.md").write_text(plan)
        artifacts["project_plan.md"] = plan

        # 2. Decisions Log
        decisions_md = self.decisions.to_markdown()
        (output_dir / "decisions_log.md").write_text(decisions_md)
        artifacts["decisions_log.md"] = decisions_md

        # 3. Task Graph
        graph = self._generate_task_graph()
        (output_dir / "task_graph.json").write_text(json.dumps(graph, indent=2))
        artifacts["task_graph.json"] = json.dumps(graph, indent=2)

        # 4. Risk Register
        risks = self._generate_risk_register()
        (output_dir / "risk_register.md").write_text(risks)
        artifacts["risk_register.md"] = risks

        # 5. Acceptance Criteria
        criteria = self._generate_acceptance_criteria()
        (output_dir / "acceptance_criteria.md").write_text(criteria)
        artifacts["acceptance_criteria.md"] = criteria

        # 6. Rollout & Rollback
        rollout = self._generate_rollout_plan()
        (output_dir / "rollout_and_rollback.md").write_text(rollout)
        artifacts["rollout_and_rollback.md"] = rollout

        logger.info(f"Generated {len(artifacts)} plan artifacts in {output_dir}")
        return artifacts

    def _generate_project_plan(self) -> str:
        """Build a structured project plan from decisions."""
        lines = [f"# Project Plan: {self.goal}\n"]

        # Extract scope decisions
        scope_decisions = [d for d in self.decisions.resolved_decisions if d.category == "scope"]
        arch_decisions = [d for d in self.decisions.resolved_decisions if d.category == "arch"]

        if scope_decisions:
            lines.append("## Scope\n")
            for d in scope_decisions:
                lines.append(f"- **{d.question}**")
                lines.append(f"  {d.answer}\n")

        if arch_decisions:
            lines.append("## Architecture\n")
            for d in arch_decisions:
                lines.append(f"- **{d.question}**")
                lines.append(f"  {d.answer}\n")

        # Generate phases from all decisions
        lines.append("## Execution Phases\n")
        lines.append("### Phase 1: Foundation")
        lines.append("- [ ] Set up project structure")
        lines.append("- [ ] Configure dependencies and tooling")
        lines.append("- [ ] Create core data models\n")

        lines.append("### Phase 2: Core Implementation")
        lines.append("- [ ] Implement primary business logic")
        lines.append("- [ ] Add API endpoints")
        lines.append("- [ ] Wire up data persistence\n")

        lines.append("### Phase 3: Integration & Testing")
        lines.append("- [ ] Write unit tests")
        lines.append("- [ ] Add integration tests")
        lines.append("- [ ] Security review\n")

        lines.append("### Phase 4: Polish & Deploy")
        lines.append("- [ ] Error handling and edge cases")
        lines.append("- [ ] Documentation")
        lines.append("- [ ] Deployment and rollout\n")

        return "\n".join(lines)

    def _generate_task_graph(self) -> dict:
        """Generate a JSON DAG of tasks with dependencies."""
        tasks = []
        task_id = 0

        # Phase 1 tasks
        for label in ["Setup project structure", "Configure dependencies", "Create data models"]:
            tasks.append({
                "id": task_id,
                "label": label,
                "phase": 1,
                "depends_on": [],
                "status": "pending",
            })
            task_id += 1

        # Phase 2 tasks depend on Phase 1
        phase1_ids = list(range(task_id))
        for label in ["Implement business logic", "Add API endpoints", "Wire persistence"]:
            tasks.append({
                "id": task_id,
                "label": label,
                "phase": 2,
                "depends_on": phase1_ids,
                "status": "pending",
            })
            task_id += 1

        # Phase 3 tasks depend on Phase 2
        phase2_ids = [t["id"] for t in tasks if t["phase"] == 2]
        for label in ["Write unit tests", "Integration tests", "Security review"]:
            tasks.append({
                "id": task_id,
                "label": label,
                "phase": 3,
                "depends_on": phase2_ids,
                "status": "pending",
            })
            task_id += 1

        return {"goal": self.goal, "tasks": tasks, "total_tasks": len(tasks)}

    def _generate_risk_register(self) -> str:
        """Generate risk register from security and deployment decisions."""
        lines = ["# Risk Register\n"]
        lines.append("| # | Risk | Likelihood | Impact | Mitigation |")
        lines.append("|---|------|-----------|--------|------------|")

        risks = [
            ("1", "Scope creep during implementation", "Medium", "High", "Strict adherence to plan phases"),
            ("2", "Security vulnerabilities in new code", "Low", "Critical", "Security scanner + manual review"),
            ("3", "Test coverage gaps", "Medium", "Medium", "Minimum coverage threshold enforcement"),
            ("4", "Integration failures with existing code", "Medium", "High", "Continuity engine checks"),
            ("5", "Performance degradation", "Low", "Medium", "Load testing before deployment"),
        ]

        # Add project-specific risks from security decisions
        security_decisions = [d for d in self.decisions.resolved_decisions if d.category == "security"]
        risk_id = 6
        for d in security_decisions:
            if d.answer:
                risks.append((
                    str(risk_id),
                    f"Security consideration: {d.question[:50]}",
                    "Medium",
                    "High",
                    d.answer[:80],
                ))
                risk_id += 1

        for risk in risks:
            lines.append(f"| {risk[0]} | {risk[1]} | {risk[2]} | {risk[3]} | {risk[4]} |")

        return "\n".join(lines)

    def _generate_acceptance_criteria(self) -> str:
        """Generate acceptance criteria from testing and scope decisions."""
        lines = ["# Acceptance Criteria\n"]

        # From scope
        scope_decisions = [d for d in self.decisions.resolved_decisions if d.category == "scope"]
        if scope_decisions:
            lines.append("## Functional Requirements\n")
            for i, d in enumerate(scope_decisions, 1):
                lines.append(f"- [ ] AC-{i}: {d.answer[:120]}")
            lines.append("")

        # From testing
        test_decisions = [d for d in self.decisions.resolved_decisions if d.category == "testing"]
        if test_decisions:
            lines.append("## Quality Requirements\n")
            for i, d in enumerate(test_decisions, 1):
                lines.append(f"- [ ] QA-{i}: {d.answer[:120]}")
            lines.append("")

        # Default criteria always present
        lines.append("## Non-Functional Requirements\n")
        lines.append("- [ ] NF-1: All tests pass (zero failures)")
        lines.append("- [ ] NF-2: Zero lint errors")
        lines.append("- [ ] NF-3: Security scan clean (no critical/high findings)")
        lines.append("- [ ] NF-4: Continuity check passes (no broken feature paths)")
        lines.append("- [ ] NF-5: Documentation updated")

        return "\n".join(lines)

    def _generate_rollout_plan(self) -> str:
        """Generate rollout and rollback plan."""
        lines = ["# Rollout & Rollback Plan\n"]

        # From deployment decisions
        deploy_decisions = [d for d in self.decisions.resolved_decisions if d.category == "deployment"]

        lines.append("## Rollout Strategy\n")
        if deploy_decisions:
            for d in deploy_decisions:
                lines.append(f"- **{d.question}**: {d.answer}")
            lines.append("")
        else:
            lines.append("- Default: Gradual rollout with feature flags")
            lines.append("- Test in staging before production")
            lines.append("")

        lines.append("## Pre-Deployment Checklist\n")
        lines.append("- [ ] All tests pass")
        lines.append("- [ ] Security scan clean")
        lines.append("- [ ] Database migrations tested")
        lines.append("- [ ] Rollback procedure verified")
        lines.append("- [ ] Monitoring/alerting configured\n")

        lines.append("## Rollback Procedure\n")
        lines.append("1. Revert Git commit(s)")
        lines.append("2. Run reverse database migration (if applicable)")
        lines.append("3. Redeploy previous version")
        lines.append("4. Verify rollback via health checks")
        lines.append("5. Notify stakeholders\n")

        lines.append("## Monitoring\n")
        lines.append("- Watch error rates for 24h post-deploy")
        lines.append("- Monitor response latency")
        lines.append("- Check credit/billing accuracy")

        return "\n".join(lines)
