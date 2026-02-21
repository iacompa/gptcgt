"""Event definitions for the gptcgt event bus.

The event-driven architecture ensures the UI never blocks on network calls.
"""

from pathlib import Path
from textual.message import Message

class TaskReceived(Message):
    """User submitted a new task."""
    def __init__(self, task_str: str, attached_files: list[Path] | None = None) -> None:
        super().__init__()
        self.task_str = task_str
        self.attached_files = attached_files or []

class FileSelected(Message):
    """User selected a file in the tree or fuzzy search."""
    def __init__(self, filepath: Path) -> None:
        super().__init__()
        self.filepath = filepath

class AgentDispatched(Message):
    """An agent call has been sent."""
    def __init__(self, agent_id: str, model_name: str) -> None:
        super().__init__()
        self.agent_id = agent_id
        self.model_name = model_name

class AgentResponseChunk(Message):
    """A streaming token chunk arrived from an agent."""
    def __init__(self, agent_id: str, chunk: str) -> None:
        super().__init__()
        self.agent_id = agent_id
        self.chunk = chunk

class AgentCompleted(Message):
    """An agent finished its full response."""
    def __init__(self, agent_id: str, full_response: str) -> None:
        super().__init__()
        self.agent_id = agent_id
        self.full_response = full_response

class PatchProposed(Message):
    """An agent is proposing code changes to a file."""
    def __init__(self, filepath: Path, diff_text: str, agent_id: str) -> None:
        super().__init__()
        self.filepath = filepath
        self.diff_text = diff_text
        self.agent_id = agent_id

class PatchApproved(Message):
    """User approved code changes."""
    def __init__(self, filepath: Path) -> None:
        super().__init__()
        self.filepath = filepath

class PatchRejected(Message):
    """User rejected code changes."""
    def __init__(self, filepath: Path) -> None:
        super().__init__()
        self.filepath = filepath

class CreditDeducted(Message):
    """Credits were consumed."""
    def __init__(self, amount: int, remaining: int) -> None:
        super().__init__()
        self.amount = amount
        self.remaining = remaining

class SecurityAlert(Message):
    """Security scan found an issue."""
    def __init__(self, severity: str, details: str, filepath: Path) -> None:
        super().__init__()
        self.severity = severity
        self.details = details
        self.filepath = filepath

class CostUpdated(Message):
    """Real-time cost tracking update."""
    def __init__(self, task_cost: float, daily_total: float) -> None:
        super().__init__()
        self.task_cost = task_cost
        self.daily_total = daily_total

class OrchestratorNarration(Message):
    """The orchestrator is narrating what it's doing / deciding."""
    def __init__(self, text: str, narration_type: str = "info") -> None:
        super().__init__()
        self.text = text
        self.narration_type = narration_type  # "info", "decision", "routing", "result", "error"

class AgentStatusUpdate(Message):
    """An agent's current activity status changed."""
    def __init__(self, agent_id: str, model_name: str, status: str, detail: str = "") -> None:
        super().__init__()
        self.agent_id = agent_id
        self.model_name = model_name  # "claude", "gpt", "gemini", "grok", "deepseek"
        self.status = status  # "thinking", "reading", "writing", "proposing", "done", "error"
        self.detail = detail  # Human-readable detail like "reading login.py and auth_middleware.py"

class VerificationUpdate(Message):
    """A verification step completed (lint, test, security scan)."""
    def __init__(self, step_name: str, passed: bool, detail: str = "") -> None:
        super().__init__()
        self.step_name = step_name  # "lint", "tests", "security", "complexity"
        self.passed = passed
        self.detail = detail  # e.g. "14/14 passed" or "SQL injection risk on line 23"

