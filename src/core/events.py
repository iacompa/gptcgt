from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from textual.message import Message


@dataclass
class ModelOutput:
    role: str
    content: str


# Existing Phase 1-4 Events


class TaskReceived(Message):
    """Emitted by ChatPanel when user submits a task."""

    def __init__(self, task_str: str, attached_files: list[Path] | None = None) -> None:
        super().__init__()
        self.task_str = task_str
        self.attached_files = attached_files or []


class FileSelected(Message):
    """Emitted when a file is selected in the file tree."""

    def __init__(self, filepath: Path) -> None:
        super().__init__()
        self.filepath = filepath


class OrchestratorNarration(Message):
    """Emitted by the orchestrator to narrate its decision process."""

    def __init__(self, text: str, narration_type: str = "info") -> None:
        super().__init__()
        self.text = text
        self.narration_type = narration_type


class MultiAgentChunk(Message):
    """Streaming text chunk from one agent in a parallel dispatch."""

    def __init__(self, dispatch_id: str, agent_id: str, text: str) -> None:
        super().__init__()
        self.dispatch_id = dispatch_id
        self.agent_id = agent_id
        self.text = text


class MultiAgentToolCall(Message):
    """Tool call from one agent in a parallel dispatch."""

    def __init__(self, dispatch_id: str, agent_id: str, tool_name: str, args: dict) -> None:
        super().__init__()
        self.dispatch_id = dispatch_id
        self.agent_id = agent_id
        self.tool_name = tool_name
        self.args = args


class ParallelAgentComplete(Message):
    """Emitted when one agent finishes in a parallel dispatch."""

    def __init__(self, dispatch_id: str, agent_id: str, result: dict) -> None:
        super().__init__()
        self.dispatch_id = dispatch_id
        self.agent_id = agent_id
        self.result = result


class ParallelDispatchStarted(Message):
    """Emitted when a parallel dispatch begins."""

    def __init__(self, dispatch_id: str, mode: str, agents: list[dict]) -> None:
        super().__init__()
        self.dispatch_id = dispatch_id
        self.mode = mode
        self.agents = agents


class ParallelDispatchComplete(Message):
    """Emitted when all agents in a parallel dispatch finish."""

    def __init__(self, dispatch: Any) -> None:
        super().__init__()
        self.dispatch = dispatch


class FileRelevanceUpdated(Message):
    """Emitted when the orchestrator identifies relevant files."""

    def __init__(self, files: list[str]) -> None:
        super().__init__()
        self.files = files


class PatchSetProposed(Message):
    """Emitted when a PatchSet or MultiAgentPatchSet is ready for review."""

    def __init__(self, patch_set: Any) -> None:
        super().__init__()
        self.patch_set = patch_set


class PatchApplied(Message):
    """Emitted after patches are applied to a file."""

    def __init__(self, filepath: str) -> None:
        super().__init__()
        self.filepath = filepath


class AgentCompleted(Message):
    """Emitted when an agent finishes its full response."""

    def __init__(self, agent_id: str, full_response: str) -> None:
        super().__init__()
        self.agent_id = agent_id
        self.full_response = full_response


class AgentStatusUpdate(Message):
    """Emitted to show agent activity in the UI."""

    def __init__(self, agent_id: str, model_name: str, status: str, detail: str = "") -> None:
        super().__init__()
        self.agent_id = agent_id
        self.model_name = model_name
        self.status = status
        self.detail = detail




class SubTaskDelegated(Message):
    """Emitted when an agent delegates a sub-task to another agent."""

    def __init__(self, parent_agent_id: str, child_model_name: str, instruction: str, depth: int) -> None:
        super().__init__()
        self.parent_agent_id = parent_agent_id
        self.child_model_name = child_model_name
        self.instruction = instruction
        self.depth = depth


class AgentDispatched(Message):
    """Emitted when any agent makes an LLM request."""

    def __init__(self, agent_name: str, model_name: str, input_tokens: int = 0) -> None:
        super().__init__()
        self.agent_name = agent_name
        self.agent_id = agent_name  # Alias for ActiveAgentsBar compatibility
        self.model_name = model_name
        self.input_tokens = input_tokens



class ExecutionPaused(Message):
    """Emitted when system enters Review state."""

    def __init__(self, reason: str = "User review requested") -> None:
        super().__init__()
        self.reason = reason


class ExecutionResumed(Message):
    """Emitted when user approves/injects prompt."""

    def __init__(self, injected_prompt: str | None = None) -> None:
        super().__init__()
        self.injected_prompt = injected_prompt


class PlanUpdated(Message):
    def __init__(self, current_step: int, total_steps: int, description: str) -> None:
        super().__init__()
        self.current_step = current_step
        self.total_steps = total_steps
        self.description = description


class ArbiterVerdictReady(Message):
    """Emitted when the arbiter produces a verdict."""

    def __init__(self, verdict: Any) -> None:
        super().__init__()
        self.verdict = verdict


# Phase 5 Events


class SpendingCapWarning(Message):
    def __init__(
        self, percent_used: float, warning_level: str, cap_dollars: float, spent_dollars: float
    ) -> None:
        super().__init__()
        self.percent_used = percent_used
        self.warning_level = warning_level
        self.cap_dollars = cap_dollars
        self.spent_dollars = spent_dollars


class CreditsUpdated(Message):
    def __init__(self, credits_remaining: int, credits_monthly: int) -> None:
        super().__init__()
        self.credits_remaining = credits_remaining
        self.credits_monthly = credits_monthly


class CreditInsufficient(Message):
    def __init__(
        self, credits_remaining: int, credits_needed: int, suggested_mode: str | None = None
    ) -> None:
        super().__init__()
        self.credits_remaining = credits_remaining
        self.credits_needed = credits_needed
        self.suggested_mode = suggested_mode


class AuthStateChanged(Message):
    def __init__(self, is_authenticated: bool, plan: str = "free", email: str = "") -> None:
        super().__init__()
        self.is_authenticated = is_authenticated
        self.plan = plan
        self.email = email


# Phase 6 Canvas Events


class CodeSelectionMade(Message):
    """Emitted when the user confirms a code selection (Enter in selection mode)."""

    def __init__(self, file_path: str, start_line: int, end_line: int, content: str) -> None:
        super().__init__()
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self.content = content


class CodeSelectionCleared(Message):
    """Emitted when the user cancels selection mode (Escape)."""

    def __init__(self) -> None:
        super().__init__()


class ContextModified(Message):
    """Emitted when context chips change (file added/removed, selection added)."""

    def __init__(
        self, action: str, file_path: str, line_range: tuple[int, int] | None = None
    ) -> None:
        super().__init__()
        self.action = action  # "add_file", "remove_file", "add_selection", "remove_selection"
        self.file_path = file_path
        self.line_range = line_range


class QuickActionTriggered(Message):
    """Emitted when a quick action button is clicked."""

    def __init__(self, action: str, context: dict) -> None:
        super().__init__()
        self.action = action  # "explain", "find_bugs", "refactor", "add_tests", etc.
        self.context = (
            context  # {"file_path": ..., "selection": ..., "start_line": ..., "end_line": ...}
        )


# Phase 6 Canvas Part 2 Events


class HunkEditStarted(Message):
    """Emitted when user begins editing a hunk's modified lines."""

    def __init__(self, file_path: str, hunk_index: int) -> None:
        super().__init__()
        self.file_path = file_path
        self.hunk_index = hunk_index


class HunkEditCompleted(Message):
    """Emitted when user finishes editing a hunk (apply or cancel)."""

    def __init__(
        self, file_path: str, hunk_index: int, edited_text: str, was_cancelled: bool = False
    ) -> None:
        super().__init__()
        self.file_path = file_path
        self.hunk_index = hunk_index
        self.edited_text = edited_text
        self.was_cancelled = was_cancelled


class AnnotationsReady(Message):
    """Emitted when annotations are parsed and ready for the UI."""

    def __init__(self, file_path: str, annotations: list[dict]) -> None:
        super().__init__()
        self.file_path = file_path
        self.annotations = annotations


class AnnotationActionClicked(Message):
    """Emitted when an action on an annotation is invoked."""

    def __init__(self, action: str, file_path: str, line_number: int, context: dict) -> None:
        super().__init__()
        self.action = action
        self.file_path = file_path
        self.line_number = line_number
        self.context = context


class CostUpdated(Message):
    """Emitted when task cost is calculated."""

    def __init__(self, task_cost: float, daily_total: float, monthly_total: float = 0.0) -> None:
        super().__init__()
        self.task_cost = task_cost
        self.daily_total = daily_total
        self.monthly_total = monthly_total


class PatchProposed(Message):
    """Emitted when a single file patch is proposed by an agent."""

    def __init__(self, filepath: Path, diff_text: str, agent_id: str) -> None:
        super().__init__()
        self.filepath = filepath
        self.diff_text = diff_text
        self.agent_id = agent_id


class SecurityAlert(Message):
    """Emitted when security scanning finds an issue."""

    def __init__(self, severity: str, details: str, filepath: Path) -> None:
        super().__init__()
        self.severity = severity
        self.details = details
        self.filepath = filepath


class VerificationUpdate(Message):
    """Emitted during arbiter verification stages."""

    def __init__(self, step_name: str, passed: bool, detail: str = "") -> None:
        super().__init__()
        self.step_name = step_name
        self.passed = passed
        self.detail = detail


class ContextTruncated(Message):
    """
    Emitted when the context manager drops history or truncates a file to fit the token budget.

    Surfaces a visible warning in the chat panel so the user understands why
    their conversation history or attached files were shortened.
    """

    def __init__(
        self,
        reason: str,
        tokens_dropped: int = 0,
        files_truncated: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.reason = reason
        self.tokens_dropped = tokens_dropped
        self.files_truncated = files_truncated or []


class ReflectionRetryHint(Message):
    """
    Emitted by the ReflectionEngine when it has distilled a lesson from a failed interaction.

    The chat panel and orchestrator can use this to surface the lesson in the UI
    and optionally pass it back into the next dispatch as an extra system message hint,
    nudging the model away from the same mistake.
    """

    def __init__(
        self,
        model_name: str,
        lesson: str,
        trigger_event: str,
    ) -> None:
        super().__init__()
        self.model_name = model_name
        self.lesson = lesson
        self.trigger_event = trigger_event


class DAGTraceEvent(Message):
    """
    Emitted by the DAG engine at each node transition for observability.  # noqa: D213

    Fields:
        node: Name of the DAG node.
        status: One of 'running', 'done', 'error'.
        elapsed_ms: Milliseconds spent in this node (0 for 'running').
        next_node: Name of the next node (only for 'done'), or None.
        error: Error message string (only for 'error'), or None.
    """

    def __init__(
        self,
        node: str,
        status: str,
        elapsed_ms: int = 0,
        next_node: str | None = None,
        error: str | None = None,
    ) -> None:
        super().__init__()
        self.node = node
        self.status = status
        self.elapsed_ms = elapsed_ms
        self.next_node = next_node
        self.error = error


# Phase 9 Events


class AgentConversation(Message):
    """
    Visible inter-agent message for the Activity Feed.  # noqa: D213

    Represents a direct message from one agent to another during
    autonomous multi-agent collaboration.
    """

    def __init__(
        self,
        from_agent: str,
        to_agent: str,
        content: str,
        msg_type: str = "info",
        iteration: int = 0,
    ) -> None:
        super().__init__()
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.content = content
        self.msg_type = msg_type  # "request", "response", "review", "approval", "question"
        self.iteration = iteration


class BudgetExceeded(Message):
    """
    Emitted when a per-task or daily budget limit is hit.  # noqa: D213

    The UI should pause execution and ask the user whether to continue.
    """

    def __init__(
        self,
        limit_type: str,
        limit_value: float,
        current_value: float,
        task_description: str = "",
    ) -> None:
        super().__init__()
        self.limit_type = limit_type  # "task_spend", "task_tokens", "daily_spend"
        self.limit_value = limit_value
        self.current_value = current_value
        self.task_description = task_description
