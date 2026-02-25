"""Active agents status bar widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Static

from src.core.events import AgentCompleted, AgentDispatched, AgentStatusUpdate

AGENT_DOTS = {
    "claude": "🟣",
    "gemini": "🔵",
    "gpt": "🟢",
    "grok": "🩷",
    "deepseek": "🟠",
}

AGENT_DISPLAY_NAMES = {
    "claude": "Claude",
    "gemini": "Gemini",
    "gpt": "ChatGPT",
    "grok": "Grok",
    "deepseek": "DeepSeek",
}


class ActiveAgentsBar(Static):
    """A small horizontal bar showing which agents are currently active."""

    DEFAULT_CSS = """
    ActiveAgentsBar {
        width: 100%;
        height: auto;
        min-height: 1;
        background: $surface;
        color: $text;
        padding: 1;
        border-bottom: solid $secondary;
    }
    """

    # We maintain a dict of active agents: agent_id -> (model_name, status)
    active_agents: reactive[dict[str, tuple[str, str]]] = reactive(dict, always_update=True)

    def compose(self) -> ComposeResult:
        yield Static("No agents active", id="active-agents-text")

    def watch_active_agents(self, active_agents: dict[str, tuple[str, str]]) -> None:
        """Update the text when the active_agents dict changes."""
        text_widget = self.query_one("#active-agents-text", Static)

        if not active_agents:
            text_widget.update("No agents active")
            return

        header = (
            f"Activity — {len(active_agents)} agent{'s' if len(active_agents) > 1 else ''} working"
        )

        agent_strings = []
        for agent_id, (model_name, status) in active_agents.items():
            dot = AGENT_DOTS.get(model_name.lower(), "⚪")
            name = AGENT_DISPLAY_NAMES.get(model_name.lower(), model_name.capitalize())
            # Format status, e.g. "writing", "reading files"
            agent_strings.append(f"{dot} {name} ({status})")

        agents_text = "   ".join(agent_strings)
        text_widget.update(f"[bold]{header}[/bold]\n{agents_text}")

    def on_agent_dispatched(self, event: AgentDispatched) -> None:
        """Add newly dispatched agent."""
        new_agents = dict(self.active_agents)
        new_agents[event.agent_id] = (event.model_name, "starting")
        self.active_agents = new_agents

    def on_agent_status_update(self, event: AgentStatusUpdate) -> None:
        """Update status of existing agent."""
        new_agents = dict(self.active_agents)
        if event.agent_id in new_agents:
            # use event.status + short detail if preferred, or just event.status
            display_status = event.status
            new_agents[event.agent_id] = (event.model_name, display_status)
        else:
            # Might happen if we missed dispatch
            new_agents[event.agent_id] = (event.model_name, event.status)
        self.active_agents = new_agents

    def on_agent_completed(self, event: AgentCompleted) -> None:
        """Remove completed agent."""
        new_agents = dict(self.active_agents)
        if event.agent_id in new_agents:
            del new_agents[event.agent_id]
        self.active_agents = new_agents
