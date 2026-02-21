from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import uuid

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING = "waiting"

@dataclass
class SubTask:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    agent_id: str | None = None
    agent_color: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cost: float = 0.0
    tokens_used: int = 0
    files_affected: list[str] = field(default_factory=list)
    error_message: str | None = None

@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    mode: str = "standard"
    quality_tier: str = "standard"
    status: TaskStatus = TaskStatus.PENDING
    subtasks: list[SubTask] = field(default_factory=list)
    cost_breakdown: object | None = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    @property
    def progress_pct(self) -> float:
        if not self.subtasks:
            return 0.0
        done = sum(1 for s in self.subtasks if s.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED))
        return (done / len(self.subtasks)) * 100.0

    @property
    def current_subtask(self) -> SubTask | None:
        for s in self.subtasks:
            if s.status == TaskStatus.IN_PROGRESS:
                return s
        return None

SUBTASK_TEMPLATES: dict[str, list[dict]] = {
    "scout": [
        {"title": "Route to fast model", "description": "Select cheapest available model"},
        {"title": "Generate response", "description": "Single model, no verification"},
    ],
    "standard": [
        {"title": "Parse intent", "description": "Classify task and extract entities"},
        {"title": "Find relevant files", "description": "Query dependency graph"},
        {"title": "Assess complexity", "description": "Assign tier 1-4"},
        {"title": "Route to agent", "description": "Select optimal model"},
        {"title": "Generate code", "description": "Agent produces solution"},
        {"title": "Security scan", "description": "Scan before presenting"},
        {"title": "Present diff", "description": "Show changes for approval"},
    ],
    "ensemble": [
        {"title": "Parse intent", "description": "Classify task"},
        {"title": "Find relevant files", "description": "Query dependency graph"},
        {"title": "Dispatch Agent A", "description": "First model"},
        {"title": "Dispatch Agent B", "description": "Second model"},
        {"title": "Arbiter: Syntax", "description": "tree-sitter validation"},
        {"title": "Arbiter: Lint", "description": "ruff/eslint"},
        {"title": "Arbiter: Tests", "description": "E2B sandbox"},
        {"title": "Arbiter: Security", "description": "semgrep/bandit"},
        {"title": "Arbiter: Score", "description": "Minimality + complexity"},
        {"title": "Present verdict", "description": "Show winner"},
    ],
    "architect": [
        {"title": "Deep analysis", "description": "Full scope analysis"},
        {"title": "Create plan", "description": "Subtask decomposition"},
        {"title": "Generate tests", "description": "Independent test agent"},
        {"title": "Dispatch Agent A", "description": "First model"},
        {"title": "Dispatch Agent B", "description": "Second model"},
        {"title": "Dispatch Agent C", "description": "Third model"},
        {"title": "Sandbox execution", "description": "Run all solutions"},
        {"title": "Full arbiter", "description": "All 6 stages"},
        {"title": "LSP cross-check", "description": "Verify references"},
        {"title": "Present verdict", "description": "Full evidence"},
    ],
}

class TaskTracker:
    def __init__(self) -> None:
        self._tasks: list[Task] = []
        self._active_task: Task | None = None

    def create_task(self, title: str, mode: str, quality_tier: str = "standard") -> Task:
        task = Task(title=title, mode=mode, quality_tier=quality_tier)
        template = SUBTASK_TEMPLATES.get(mode, SUBTASK_TEMPLATES["standard"])
        for st in template:
            task.subtasks.append(SubTask(title=st["title"], description=st["description"]))
        self._tasks.insert(0, task)
        self._active_task = task
        return task

    def start_subtask(self, task_id: str, subtask_id: str, agent_id: str | None = None, agent_color: str | None = None) -> None:
        task = self._get_task(task_id)
        if task:
            st = self._get_subtask(task, subtask_id)
            if st:
                st.status = TaskStatus.IN_PROGRESS
                st.started_at = datetime.now()
                st.agent_id = agent_id
                st.agent_color = agent_color

    def complete_subtask(self, task_id: str, subtask_id: str, cost: float = 0.0, tokens: int = 0, files: list[str] | None = None) -> None:
        task = self._get_task(task_id)
        if task:
            st = self._get_subtask(task, subtask_id)
            if st:
                st.status = TaskStatus.COMPLETED
                st.completed_at = datetime.now()
                st.cost = cost
                st.tokens_used = tokens
                if files:
                    st.files_affected.extend(files)

    def fail_subtask(self, task_id: str, subtask_id: str, error: str) -> None:
        task = self._get_task(task_id)
        if task:
            st = self._get_subtask(task, subtask_id)
            if st:
                st.status = TaskStatus.FAILED
                st.completed_at = datetime.now()
                st.error_message = error
                task.status = TaskStatus.FAILED

    def wait_subtask(self, task_id: str, subtask_id: str) -> None:
        task = self._get_task(task_id)
        if task:
            st = self._get_subtask(task, subtask_id)
            if st:
                st.status = TaskStatus.WAITING

    def complete_task(self, task_id: str) -> None:
        task = self._get_task(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            if self._active_task and self._active_task.id == task_id:
                self._active_task = None

    def get_active_task(self) -> Task | None:
        return self._active_task

    def get_task_history(self) -> list[Task]:
        return list(self._tasks)

    def _get_task(self, task_id: str) -> Task | None:
        for t in self._tasks:
            if t.id == task_id:
                return t
        return None

    def _get_subtask(self, task: Task, subtask_id: str) -> SubTask | None:
        for st in task.subtasks:
            if st.id == subtask_id:
                return st
        return None
