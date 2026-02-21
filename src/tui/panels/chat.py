"""Chat panel displaying persistent message history."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll, Vertical
from textual.widgets import Static, Markdown
from textual.reactive import reactive

from src.core.chat_store import ChatMessage, MessageRole, ChatStore

class ChatMessageContainer(Static):
    """Container for a single chat message."""
    pass

class ChatPanel(Vertical):
    """Right panel (or middle panel if activity feed is right) for the UI. Wait, specs say:
    'Chat Panel (Phase 2, after Prompt 2.6)... right panel'
    We will create this component and it will be swapped in app.py or used as center.
    """
    
    DEFAULT_CSS = """
    ChatPanel {
        width: 100%;
        height: 100%;
        border-right: solid #30363D;
    }
    #chat-scroll {
        width: 100%;
        height: 1fr;
        overflow-y: auto;
    }
    .chat-msg-user {
        margin: 1;
        padding: 1;
        background: #1C2333; /* Darker accent */
        border-left: solid #58A6FF;
    }
    .chat-msg-agent {
        margin: 1;
        padding: 1;
        border-left: solid #A78BFA;
    }
    .chat-msg-orchestrator {
        color: #8B949E;
        text-style: italic;
        padding: 0 1;
    }
    .chat-msg-header {
        text-style: bold;
        color: #94A3B8;
        margin-bottom: 1;
    }
    .chat-cost {
        color: #8B949E;
        text-align: right;
    }
    """

    def __init__(self, chat_store: ChatStore, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chat_store = chat_store
        self._auto_scroll = True

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="chat-scroll"):
            yield Static("")

    def on_mount(self) -> None:
        """Load persistent history on mount."""
        messages = self.chat_store.get_session_messages()
        for msg in messages:
            self.append_message(msg, scroll=False)
        self._scroll_to_bottom()

    def append_message(self, msg: ChatMessage, scroll: bool = True) -> None:
        """Append a new message to the panel."""
        scroll_view = self.query_one("#chat-scroll", VerticalScroll)
        
        # Determine CSS class based on role
        if msg.role == MessageRole.USER:
            classes = "chat-msg-user"
            header = f"You • {msg.timestamp.strftime('%H:%M:%S')}"
        elif msg.role == MessageRole.AGENT:
            classes = "chat-msg-agent"
            # Hardcoded claude-purple as default fallback
            c_str = msg.agent_id or "Agent"
            header = f"{c_str} • {msg.timestamp.strftime('%H:%M:%S')}"
            if msg.cost is not None:
                header += f" • ${msg.cost:.4f}"
        elif msg.role == MessageRole.ORCHESTRATOR:
            classes = "chat-msg-orchestrator"
            header = ""
        else:
            classes = ""
            header = "System"
            
        container = ChatMessageContainer(classes=classes)
        with container.app.batch_update():
            scroll_view.mount(container)
            if header:
                container.mount(Static(header, classes="chat-msg-header"))
            
            if msg.role == MessageRole.ORCHESTRATOR:
                container.mount(Static(msg.content))
            else:
                container.mount(Markdown(msg.content))

        if scroll and self._auto_scroll:
            self.call_after_refresh(self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        scroll_view = self.query_one("#chat-scroll", VerticalScroll)
        scroll_view.scroll_end(animate=False)

    def on_vertical_scroll_scroll_changed(self, event: VerticalScroll.ScrollChanged) -> None:
        """Disable auto-scroll if the user scrolls up."""
        # if event.y < event.y_max means the user scrolled up
        if event.y < event.y_max - 2: # small buffer
            self._auto_scroll = False
        else:
            self._auto_scroll = True
