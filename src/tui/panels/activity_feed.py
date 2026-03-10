"""Activity Feed Panel displaying real-time orchestrator narration and agent status."""

from __future__ import annotations

import datetime

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static

from src.core.events import (
    AgentCompleted,
    AgentConversation,
    AgentDispatched,
    AgentStatusUpdate,
    BudgetExceeded,
    CostUpdated,
    DAGTraceEvent,
    OrchestratorNarration,
    PatchProposed,
    SecurityAlert,
    VerificationUpdate,
)
from src.tui.widgets.active_agents_bar import AGENT_DISPLAY_NAMES, AGENT_DOTS, ActiveAgentsBar


class ActivityEntry(Static):
    """A single entry in the activity feed."""

    DEFAULT_CSS = """
    ActivityEntry {
        padding: 0 1;
        width: 100%;
        height: auto;
    }
    """


class ActivityFeedPanel(Vertical):
    """Right panel displaying real-time agent activity."""

    DEFAULT_CSS = """
    ActivityFeedPanel {
        border-left: solid $secondary;
        width: 100%;
        height: 100%;
    }
    #feed-scroll {
        width: 100%;
        height: 1fr;
        overflow-y: auto;
    }
    """

    def compose(self) -> ComposeResult:
        # Top bar
        yield ActiveAgentsBar(id="active-agents-bar")
        # Scrollable feed
        with VerticalScroll(id="feed-scroll"):
            yield ActivityEntry("🎯 Orchestrator: System ready.", classes="activity-orchestrator")

    def _add_entry(self, markup: str, is_orchestrator: bool = False) -> None:
        """Add a new entry to the feed and scroll to bottom."""
        feed = self.query_one("#feed-scroll", VerticalScroll)

        # Add timestamp
        now = datetime.datetime.now().strftime("%H:%M:%S")
        timestamp_markup = f"[span classes='activity-timestamp']{now}[/span] "

        classes = "activity-entry activity-orchestrator" if is_orchestrator else "activity-entry"
        entry = ActivityEntry(timestamp_markup + markup, classes=classes)

        feed.mount(entry)

        # Limit to 200 entries
        entries = feed.query(ActivityEntry)
        if len(entries) > 200:
            entries.first().remove()

        feed.scroll_end(animate=False)

    # Note: Event handlers receive messages propagated down from app,
    # or bubbled up from children. Let's make sure we catch them.

    def on_orchestrator_narration(self, event: OrchestratorNarration) -> None:
        self._add_entry(f"🎯 Orchestrator: {event.text}", is_orchestrator=True)

    def on_agent_status_update(self, event: AgentStatusUpdate) -> None:
        model_name = event.model_name or "unknown"
        dot = AGENT_DOTS.get(model_name.lower(), "⚪")
        name = AGENT_DISPLAY_NAMES.get(model_name.lower(), model_name.capitalize())

        verb = {
            "thinking": "is thinking...",
            "reading": f"is reading {event.detail}",
            "writing": f"is writing changes to {event.detail}",
            "proposing": f"is proposing changes — {event.detail}",
            "done": f"finished. {event.detail}",
            "error": f"hit an error: {event.detail}",
        }.get(event.status, event.detail)

        self._add_entry(f"{dot} {name} {verb}")

        # Propagate to status bar
        self.query_one("#active-agents-bar").on_agent_status_update(event)

    def on_verification_update(self, event: VerificationUpdate) -> None:
        icon = "✅" if event.passed else "❌"
        self._add_entry(f"   {icon} {event.step_name}: {event.detail}")

    def on_agent_dispatched(self, event: AgentDispatched) -> None:
        model_name = event.model_name or "unknown"
        dot = AGENT_DOTS.get(model_name.lower(), "⚪")
        name = AGENT_DISPLAY_NAMES.get(model_name.lower(), model_name.capitalize())
        self._add_entry(f"🎯 Orchestrator: Dispatching {name} {dot}", is_orchestrator=True)
        # Propagate to status bar
        self.query_one("#active-agents-bar").on_agent_dispatched(event)

    def on_agent_completed(self, event: AgentCompleted) -> None:
        self._add_entry(f"🎯 Orchestrator: Agent {event.agent_id} completed response.", is_orchestrator=True)
        # Propagate to status bar
        self.query_one("#active-agents-bar").on_agent_completed(event)

    def on_cost_updated(self, event: CostUpdated) -> None:
        self._add_entry(f"   💰 Task cost: ${event.task_cost:.3f} | Today: ${event.daily_total:.2f}")

    def on_patch_proposed(self, event: PatchProposed) -> None:
        self._add_entry(f"   📝 Patch proposed for {event.filepath.name} by {event.agent_id}")

    def on_security_alert(self, event: SecurityAlert) -> None:
        icon = "🔴" if event.severity == "high" else "🟡"
        self._add_entry(f"   {icon} Security Alert ({event.severity}): {event.details} in {event.filepath.name}")

    def on_dag_trace_event(self, event: DAGTraceEvent) -> None:
        """Render DAG node transitions as concise activity entries."""
        name = event.node.replace("_", " ").title()
        if event.status == "running":
            self._add_entry(f"   ⏳ {name}...", is_orchestrator=True)
        elif event.status == "done":
            elapsed = f"{event.elapsed_ms}ms" if event.elapsed_ms else ""
            arrow = f" → {event.next_node.replace('_', ' ').title()}" if event.next_node else ""
            self._add_entry(f"   ✓ {name} ({elapsed}){arrow}", is_orchestrator=True)
        elif event.status == "error":
            self._add_entry(
                f"   ✗ {name} — {event.error or 'unknown error'}",
                is_orchestrator=True,
            )

    # Phase 9: Inter-agent conversation rendering

    _AGENT_ICONS = {
        "coder": "💻",
        "tester": "🧪",
        "arbiter": "⚖️",
        "scout": "🔍",
        "orchestrator": "🎯",
        "architect": "📐",
    }

    def on_agent_conversation(self, event: AgentConversation) -> None:
        """Render inter-agent messages as a visible conversation."""
        from_icon = self._AGENT_ICONS.get(event.from_agent, "🤖")
        to_icon = self._AGENT_ICONS.get(event.to_agent, "🤖")
        iter_tag = f"[{event.iteration}] " if event.iteration else ""
        self._add_entry(f"   {iter_tag}{from_icon} → {to_icon}: {event.content}")

    def on_budget_exceeded(self, event: BudgetExceeded) -> None:
        """Show a prominent budget warning in the feed."""
        if event.limit_type == "task_spend":
            msg = f"⛔ Task budget reached: ${event.current_value:.2f} / ${event.limit_value:.2f}"
        elif event.limit_type == "task_tokens":
            msg = f"⛔ Token limit reached: {int(event.current_value):,} / {int(event.limit_value):,}"
        else:
            msg = f"⛔ Daily budget reached: ${event.current_value:.2f} / ${event.limit_value:.2f}"
        self._add_entry(msg, is_orchestrator=True)
