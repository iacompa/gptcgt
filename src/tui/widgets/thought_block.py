import time

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Collapsible, Label


class AgentThoughtBlock(Collapsible):
    """
    An interactive, collapsible UI component for the Chat Panel.
    Used to cleanly hide internal Agent thinking loops (like Tool executions, Sandboxing, or Swarm handoffs)
    behind a clickable accordion displaying the elapsed thought time.
    """

    DEFAULT_CSS = """
    AgentThoughtBlock {
        margin: 0 1;
        padding: 0;
        width: 100%;
        background: $surface;
        border: solid $secondary;
        border-title-color: $text-muted;
    }

    AgentThoughtBlock:focus {
        border: solid $primary;
    }

    .thought-content {
        color: $text-muted;
        text-style: italic;
        padding: 1;
        width: 100%;
    }
    """

    def __init__(self, title: str = "💭 Thinking...", content: str = "", **kwargs) -> None:
        super().__init__(title=title, **kwargs)
        self.raw_content = content
        self.start_timer = time.monotonic()
        self._content_label = Label(content, classes="thought-content")
        self.collapsed = True

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield self._content_label

    def append_thought(self, text: str) -> None:
        """Stream data into the thought block dynamically."""
        self.raw_content += text
        self._content_label.update(self.raw_content)

    def complete_thought(self, final_title: str | None = None) -> None:
        """Lock the block and append physical elapsed time to the Title string."""
        elapsed = time.monotonic() - self.start_timer
        t_title = final_title if final_title else "💭 Thought Process"
        self.title = f"{t_title} ({elapsed:.1f}s)"
