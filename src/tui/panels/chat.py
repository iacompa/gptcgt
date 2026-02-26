from __future__ import annotations

import re
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import MouseDown
from textual.message import Message
from textual.widgets import Label, Static, TextArea

from src.core.events import (
    AgentStatusUpdate,
    ArbiterVerdictReady,
    ContextModified,
    ContextTruncated,
    MultiAgentChunk,
    MultiAgentToolCall,
    OrchestratorNarration,
    ParallelAgentComplete,
    ParallelDispatchComplete,
    ParallelDispatchStarted,
    ReflectionRetryHint,
    TaskReceived,
)
from src.core.logger import get_logger
from src.tui.widgets.context_chips import ContextChipBar


def apply_brand_colors(text: str) -> str:
    def replacer(match):
        w = match.group(0)
        lw = w.lower()
        if lw in ("chatgpt", "gpt", "chat", "openai"):
            color = "#34D399"  # Green
        elif lw in ("claude", "sonnet", "opus", "haiku", "anthropic"):
            color = "#FB923C"  # Orange
        elif lw in ("gemini", "deepseek", "google"):
            color = "#60A5FA"  # Blue
        elif lw in ("grok", "xai"):
            color = "#9CA3AF"  # Grey
        elif lw in ("teamtalk", "team", "talk"):
            color = "#A78BFA"  # Purple
        elif lw == "openrouter":
            color = "#F43F5E"  # Pink
        else:
            return w
        return f"[{color}]{w}[/{color}]"

    # Skip processing if it looks like there are markup tags to avoid nesting errors
    if "[" in text and "]" in text:
        return text

    return re.sub(r'\b(chatgpt|gpt|chat|openai|claude|sonnet|opus|haiku|anthropic|grok|xai|gemini|deepseek|google|teamtalk|team|talk|openrouter)\b', replacer, text, flags=re.IGNORECASE)  # noqa: E501

class AnimatedWelcome(Static):
    DEFAULT_CSS = """
    AnimatedWelcome {
        text-align: center;
        padding: 0;
        margin-bottom: 1;
        width: 100%;
    }
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.step = 0
        self.frames = [
            [("ChatGPT", "#34D399"), (" ", ""), ("Claude", "#FB923C"), (" ", ""), ("Grok", "#9CA3AF"), (" ", ""), ("Gemini", "#60A5FA"), (" ", ""), ("TeamTalk", "#A78BFA")],  # noqa: E501
            [("hatGPT", "#34D399"), (" ", ""), ("Claud", "#FB923C"), (" ", ""), ("rok", "#9CA3AF"), (" ", ""), ("Gemin", "#60A5FA"), (" ", ""), ("eamTal", "#A78BFA")],  # noqa: E501
            [("atGPT", "#34D399"), (" ", ""), ("Clau", "#FB923C"), (" ", ""), ("ok", "#9CA3AF"), (" ", ""), ("Gemi", "#60A5FA"), (" ", ""), ("amTa", "#A78BFA")],  # noqa: E501
            [("tGPT", "#34D399"), (" ", ""), ("Cla", "#FB923C"), (" ", ""), ("k", "#9CA3AF"), (" ", ""), ("Gem", "#60A5FA"), (" ", ""), ("mT", "#A78BFA")],  # noqa: E501
            [("GPT", "#34D399"), (" ", ""), ("Cl", "#FB923C"), (" ", ""), ("", "#9CA3AF"), ("", ""), ("Ge", "#60A5FA"), (" ", ""), ("T", "#A78BFA")],  # noqa: E501
            [("GPT", "#34D399"), (" ", ""), ("C", "#FB923C"), (" ", ""), ("", "#9CA3AF"), ("", ""), ("G", "#60A5FA"), (" ", ""), ("T", "#A78BFA")],  # noqa: E501
            [("GPT", "#34D399"), ("C", "#FB923C"), ("G", "#60A5FA"), ("T", "#A78BFA")],
            [("gpt", "#34D399"), ("c", "#FB923C"), ("g", "#60A5FA"), ("t", "#A78BFA")],
        ]

    def on_mount(self) -> None:
        self.timer = self.set_interval(0.3, self.tick)

    def tick(self) -> None:
        if self.step < len(self.frames) - 1:
            self.step += 1
            self.refresh()
        else:
            self.timer.stop()

    def render(self) -> Text:
        t = Text(justify="center")
        t.append("\nWelcome to ", style="bold")

        for text_part, color in self.frames[min(self.step, len(self.frames) - 1)]:
            style_str = f"{color} bold" if color else "bold"
            t.append(text_part, style=style_str)

        t.append(" 👋\n\nTry asking:", style="bold")
        return t

logger = get_logger("tui.chat")

_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class ChatMessage(Static):
    """Renders a single chat message (User, Agent, System)."""

    DEFAULT_CSS = """
    ChatMessage {
        width: 100%;
        height: auto;
        margin-bottom: 1;
        padding: 0;
    }
    /* ── User bubble: right-aligned ────────────────────── */
    .msg-user {
        align: right top;
        width: 100%;
        padding: 0 1;
    }
    .msg-user-inner {
        background: $primary;
        color: $background;
        padding: 1 2;
        width: auto;
        max-width: 78%;
        border: blank;
    }
    .msg-user > .msg-header {
        content-align: right middle;
        color: $background;
        text-style: bold;
        margin-bottom: 0;
        width: auto;
    }
    /* ── Agent bubble: left-aligned ────────────────────── */
    .msg-agent {
        align: left top;
        width: 100%;
        padding: 0 1;
    }
    .msg-agent-inner {
        background: $surface;
        padding: 1 2;
        width: auto;
        max-width: 90%;
        border-left: thick $primary;
    }
    .msg-agent > .msg-header {
        content-align: left middle;
        text-style: bold;
        margin-bottom: 0;
        width: auto;
    }
    /* ── System message ────────────────────────────────── */
    .msg-system {
        color: $text-muted;
        text-align: center;
        padding: 0 1;
        margin: 0;
        width: 100%;
    }
    /* ── Transient thinking pill ───────────────────────── */
    .transient-pill {
        padding: 0 2;
        color: $primary;
        text-style: italic;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("c", "copy", "Copy message", show=True),
    ]

    content: str = ""
    _current_streaming_label: Label | None = None
    _streaming_labels: list[Label] = []
    _current_streaming_text: str = ""

    def __init__(self, role: str, content: str, name: str = "", time_str: str = "", **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content = content
        self.speaker_name = name
        self.time_str = time_str

        from src.tui.widgets.collapsible_code import StreamingCodeParser

        self.parser = StreamingCodeParser()
        # The following were moved to class attributes with default values:
        # self._streaming_labels: list[Label] = []
        # self._current_streaming_label: Label | None = None

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical as _V
        if self.role == "system":
            self.add_class("msg-system")
            yield Label(f"── {self.content} ── {self.time_str} ──")
        elif self.role == "user":
            self.add_class("msg-user")
            with _V(classes="msg-user-inner"):
                yield Label(f"[bold]You[/bold]  [dim]{self.time_str}[/dim]", classes="msg-header")
                content_label = Label(apply_brand_colors(self.content))
                content_label.styles.width = "auto"
                yield content_label
        else:
            self.add_class("msg-agent")
            with _V(classes="msg-agent-inner"):
                header = f"{self.speaker_name}  [dim]{self.time_str}[/dim]"
                self._header_label = Label(apply_brand_colors(header), classes="msg-header")
                yield self._header_label

                if self.content:
                    from src.tui.widgets.collapsible_code import (
                        CollapsibleCodeBlock,
                        parse_agent_response,
                    )
                    blocks = parse_agent_response(self.content)
                    for block in blocks:
                        if block.is_code:
                            yield CollapsibleCodeBlock(language=block.language, code=block.content)
                        else:
                            label = Label(apply_brand_colors(block.content))
                            label.styles.width = "auto"
                            yield label


    def update_speaker(self, name: str) -> None:
        """Dynamically update the speaker's name in the UI header."""
        self.speaker_name = name
        if hasattr(self, "_header_label"):
            self._header_label.update(apply_brand_colors(f"{self.speaker_name}  [dim]{self.time_str}[/dim]"))

        if not self.content:
            # First chunk incoming — mount streaming label inside inner container
            inner = next((c for c in self.children if "msg-agent-inner" in c.classes), self)
            self._current_streaming_label = Label("")
            self._streaming_labels.append(self._current_streaming_label)
            inner.mount(self._current_streaming_label)

    def append_chunk(self, chunk: str) -> None:
        if not self.is_mounted:
            return

        self.content += chunk

        from src.tui.widgets.collapsible_code import CollapsibleCodeBlock

        events = self.parser.feed(chunk)

        for event_type, data in events:
            if event_type == "text":
                if self._current_streaming_label is None:
                    self._current_streaming_label = Label("")
                    self._streaming_labels.append(self._current_streaming_label)
                    self.mount(self._current_streaming_label)

                self._current_streaming_text += data
                self._current_streaming_label.update(apply_brand_colors(self._current_streaming_text))

            elif event_type == "code_start":
                self._current_streaming_label = None
                self._current_streaming_text = ""

            elif event_type == "code_end":
                lang = data["language"]
                code_text = data["full_code"]
                self.mount(CollapsibleCodeBlock(language=lang, code=code_text))
                self._current_streaming_text = ""

    def finalize_streaming(self) -> None:
        """Call this when agent is done sending chunks."""
        if not self.is_mounted:
            return

        from src.tui.widgets.collapsible_code import CollapsibleCodeBlock

        events = self.parser.finalize()

        for event_type, data in events:
            if event_type == "text":
                if self._current_streaming_label is None:
                    self._current_streaming_label = Label("")
                    self._streaming_labels.append(self._current_streaming_label)
                    self.mount(self._current_streaming_label)

                self._current_streaming_text += data
                self._current_streaming_label.update(apply_brand_colors(self._current_streaming_text))

            elif event_type == "code_end":
                lang = data["language"]
                code_text = data["full_code"]
                self.mount(CollapsibleCodeBlock(language=lang, code=code_text))
                self._current_streaming_text = ""

    def append_thought(self, title: str, content: str) -> None:
        """Intercepts internal thinking loops and mounts the Collapsible."""
        if not self.is_mounted:
            return

        from src.tui.widgets.thought_block import AgentThoughtBlock
        block = AgentThoughtBlock(title=title, content=content)

        # Break current label stream to mount block linearly
        self._current_streaming_label = None
        self._current_streaming_text = ""
        self.mount(block)


class AgentStreamBox(Static):
    """Renders a single agent's stream within a parallel execution container."""

    DEFAULT_CSS = """
    AgentStreamBox {
        width: 90%;
        margin-right: 10;
        height: auto;
        min-height: 5;
        border: blank;
        background: transparent;
        margin-bottom: 2;
        padding: 0 2;
    }
    .asb-header {
        width: 100%;
        background: transparent;
        color: $text-muted;
        text-align: left;
        text-style: bold;
        margin-bottom: 1;
    }
    .asb-content {
        height: auto;
        color: $text-muted;
    }
    .asb-tools {
        color: $primary;
        font-style: italic;
        margin-top: 1;
    }
    .asb-footer {
        width: 100%;
        color: $text-muted;
        text-align: right;
        margin-top: 1;
        border-top: none;
    }
    """

    def __init__(self, agent_id: str, model_name: str, emoji: str, color: str, **kwargs):
        super().__init__(**kwargs)
        self.agent_id = agent_id
        self.model_name = model_name
        self.emoji = emoji
        self.color = color
        self.content_text = ""
        self.content_label: Label | None = None
        self.footer_label: Label | None = None
        self.tool_logs: list["CollapsibleCodeBlock"] = []  # noqa: F821

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical

        yield Label(f"[{self.color}]{self.emoji} {self.model_name}[/]", classes="asb-header")

        self.content_label = Label(self.content_text, classes="asb-content")
        yield self.content_label

        self.tools_container = Vertical(classes="asb-tools-container")
        yield self.tools_container

        self.footer_label = Label("⏱️ waiting...", classes="asb-footer")
        yield self.footer_label

    def append_chunk(self, chunk: str) -> None:
        self.content_text += chunk
        display_text = (
            self.content_text[-500:] if len(self.content_text) > 500 else self.content_text
        )
        if len(self.content_text) > 500:
            display_text = "..." + display_text

        if self.content_label and self.content_label.is_mounted:
            try:
                self.content_label.update(apply_brand_colors(display_text))
            except Exception as e:
                logger.debug(f"ContentLabel update failed: {e}")

    def add_tool_call(self, tool_name: str, args: dict) -> None:
        import json

        from src.tui.widgets.collapsible_code import CollapsibleCodeBlock

        args_str = json.dumps(args, indent=2)

        # Phase 11: Live Tool Streaming UI Placeholder
        # This will hold the args initially, and in the future can receive streaming tool output
        block = CollapsibleCodeBlock(language="json", code=args_str)
        # Customizing the title of the Collapsible inside the block

        # We mount it in the tools container
        self.tools_container.mount(block)

        # Keep track to potentially stream output into it later
        self.tool_logs.append(block)

    def mark_complete(self, duration_ms: int, cost_usd: float) -> None:
        if self.footer_label:
            self.footer_label.update(f"✓ {duration_ms / 1000:.1f}s │ ${cost_usd:.4f}")

    def mark_error(self, error: str) -> None:
        if self.footer_label:
            self.footer_label.update("❌ Error")
        if self.content_label:
            self.content_label.update(f"[red]{error}[/red]")


class ChatInput(TextArea):
    """Multi-line expanding text area with Ctrl+Enter to send and @ autocomplete."""

    BINDINGS = [
        Binding("enter", "submit", "Send Task", priority=True),
        Binding("shift+enter", "newline", "New Line", priority=True),
        Binding("ctrl+enter", "submit", "Send Task"),
        Binding("f9", "submit", "Send Task"),
        Binding("ctrl+s", "submit", "Send Task"),
    ]

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    def action_newline(self) -> None:
        """Insert a newline at the cursor."""
        self.insert("\n")

    def action_submit(self) -> None:
        text = self.text.strip()
        if text:
            logger.info(f"Chat input submitted: {text.splitlines()[0][:50]}...")
            self.post_message(self.Submitted(text))
            self.text = ""


class ChatPanel(Vertical):
    """The main right panel where the user talks to AI agents."""

    DEFAULT_CSS = """
    ChatPanel {
        width: 1fr;
        height: 100%;
        background: $background;
    }
    #chat-scroll {
        height: 1fr;
        width: 100%;
        overflow-y: scroll;
        overflow-x: hidden;
        padding: 1 1;
    }
    #chat-input-container {
        height: auto;
        min-height: 5;
        max-height: 15;
        border-top: none;
        background: transparent;
        padding: 1 2;
    }
    #chat-input-header {
        display: block;
        height: 1;
        color: $text-muted;
        padding: 0 2;
        background: $surface;
        border-top: solid $secondary;
    }
    #chat-input {
        min-height: 3;
        height: auto;
        max-height: 10;
        background: $surface;
        margin-bottom: 0;
        border: blank;
        padding: 1 2;
    }
    #chat-input-hint {
        display: block;
        height: 1;
        color: $text-muted;
        padding: 0 2;
        text-align: right;
    }
    .empty-prompt {
        text-align: center;
        margin-bottom: 1;
        padding: 1 2;
        background: $surface;
        color: $text;
        border: blank;
        width: 100%;
        content-align: center middle;
    }
    .empty-prompt:hover {
        background: $panel;
        text-style: bold;
        color: $accent;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._user_scrolled_up = False
        self._parallel_containers: dict[str, Horizontal] = {}  # dispatch_id -> container
        self._agent_boxes: dict[
            str, dict[str, AgentStreamBox]
        ] = {}  # dispatch_id -> {agent_id -> box}
        self._pending_reflection_hint: str | None = None  # stores latest lesson for next dispatch

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="chat-scroll") as scroll:
            self.scroll_container = scroll

        with Vertical(id="chat-input-container"):
            yield Label("⚡ Standard │ Mode: Standard │ 5 cr", id="chat-input-header")
            self.context_chips = ContextChipBar(id="context-chips")
            yield self.context_chips
            self.input_area = ChatInput(id="chat-input")
            self.input_area.show_line_numbers = False
            self.input_area.soft_wrap = True
            yield self.input_area
            yield Label("Press [bold]Enter[/bold] to send • [bold]Shift+Enter[/bold] for newline", id="chat-input-hint")

    def on_mount(self) -> None:
        if hasattr(self, "input_area"):
            self.input_area.theme = "github_light" if getattr(self.app, "theme", "") == "polar" else "vscode_dark"
        if hasattr(self.app, "chat_store"):
            self._load_session_history()

    def _load_session_history(self) -> None:
        """Load messages from the active session."""
        # Clear existing messages and prompts
        to_remove = []
        for child in self.scroll_container.children:
            to_remove.append(child)
        for child in to_remove:
            child.remove()

        # Load messages
        if not hasattr(self.app, "chat_store"):
            return

        session_id = self.app.chat_store.current_session_id
        messages = self.app.chat_store.get_session_messages(session_id)
        if not messages:
            # Re-mount empty state if no messages
            self.scroll_container.mount(AnimatedWelcome())
            self.scroll_container.mount(
                Label('• "Explain this codebase"', classes="empty-prompt", id="ep-1")
            )
            self.scroll_container.mount(
                Label('• "Fix the bug in auth.py"', classes="empty-prompt", id="ep-2")
            )
            self.scroll_container.mount(
                Label('• "Ask Gemini to write tests"', classes="empty-prompt", id="ep-3")
            )
            self.scroll_container.mount(
                Label('• "Refactor this function"', classes="empty-prompt", id="ep-4")
            )
            self.scroll_container.mount(
                Label(
                    "\nReference files with @filename\nChange tier with Ctrl+Q\nAll shortcuts: Ctrl+?",  # noqa: E501
                    classes="msg-system",
                )
            )
            return

        for msg in messages:
            self._append_message(msg.role.value, msg.content, time_str="")

    def on_click(self, event) -> None:
        """Handle clicking on empty state prompts."""
        if isinstance(event.widget, Label) and "empty-prompt" in event.widget.classes:
            raw = str(event.widget.render())
            text = raw.replace('• "', "").replace('"', "")
            self.input_area.text = text
            self.input_area.focus()

    @on(ChatInput.Changed)
    def on_input_changed(self, event: ChatInput.Changed) -> None:
        # Dynamic Token Estimation while typing
        try:
            import textual.app as _tapp

            from src.core.model_registry import ModelRegistry
            current_app = _tapp.active_app.get()
            if hasattr(current_app, "status_bar"):
                # Rough token estimate: length / 4
                tokens = len(event.value) // 4

                # Fetch currently assigned active mode limits
                tier = current_app.status_bar.tier_name.lower()

                # Normalize tier to valid enum values (fix: was testing for 'heavy' which doesn't exist)
                _valid_tiers = {"light", "standard", "max"}
                if tier not in _valid_tiers:
                    tier = "standard"

                from src.core.model_registry import QualityTier
                from src.core.router import CodingRouter

                router = CodingRouter()
                q_tier = QualityTier(tier)
                model_def = router.route_task("chat", 5, q_tier, role="coder")

                if model_def:
                    registry = ModelRegistry()
                    est_dollars = registry.calculate_cost(model_def.id, prompt_tokens=tokens, completion_tokens=0)
                    # BUGFIX: was `app.status_bar` (NameError) → `current_app.status_bar`
                    current_app.status_bar.est_cost = est_dollars
        except Exception as e:
            logger.debug(f"Token estimation failed: {e}")

    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        text = event.text

        # Check for commands first
        if text.startswith("/"):
            self._handle_slash_command(text)
            return

        # Check for API keys
        from src.auth.keychain import KeyChainManager

        if not KeyChainManager.has_any_keys() and not self.app.config.user.setup_completed:
            self._append_message(
                "system", "⚠️ No API keys configured. Add a key in Settings (Ctrl+,) or run /setup"
            )
            return

        # Render user message
        from datetime import datetime

        time_str = datetime.now().strftime("%I:%M %p")
        self._append_message("user", text, time_str=time_str)

        # Extract @file references
        files = re.findall(r"@([a-zA-Z0-9_\-\./]+)", text)
        clean_text = re.sub(r"@[a-zA-Z0-9_\-\./]+", "", text).strip()

        # Security: validate @file paths against workspace root
        file_paths = []
        try:
            from src.core.workspace import Workspace
            ws = Workspace.get_instance()
            project_root = ws.get_project_root()
            for f in files:
                resolved = (project_root / f).resolve()
                if str(resolved).startswith(str(project_root)):
                    file_paths.append(Path(f))
                else:
                    logger.warning(f"@file path rejected (outside workspace): {f}")
        except Exception:
            file_paths = [Path(f) for f in files]

        # Include context from chips
        for ctx in self.context_chips.get_context_summary():
            if ctx["chip_type"] == "file":
                p = Path(ctx["file_path"])
                if p not in file_paths:
                    file_paths.append(p)
            elif ctx["chip_type"] == "selection":
                rng = ctx.get("line_range")
                if rng:
                    # Append selection info to task text
                    clean_text += (
                        f"\n\n[Context: {Path(ctx['file_path']).name} lines {rng[0]}-{rng[1]}]"
                    )

        # Emit properly structured task received event
        self.post_message(TaskReceived(task_str=clean_text, attached_files=file_paths))

        # Show animated thinking spinner before first AI token
        self._start_thinking_spinner()

        # Clear context chips after sending
        self.context_chips.clear_all()

    def _start_thinking_spinner(self) -> None:
        """Mount an animated spinner pill in the chat. Removed on first token."""
        from textual.widgets import Static
        self._spinner_label = Static("⠋ Thinking...", classes="transient-pill")
        self._spinner_frame = 0
        self.scroll_container.mount(self._spinner_label)
        self.scroll_container.scroll_end(animate=False)
        self._spinner_timer = self.set_interval(
            0.1, self._tick_spinner
        )

    def _tick_spinner(self) -> None:
        """Advance the spinner animation frame."""
        if not hasattr(self, "_spinner_label") or self._spinner_label is None:
            return
        try:
            frame = _SPINNER_FRAMES[self._spinner_frame % len(_SPINNER_FRAMES)]
            self._spinner_label.update(f"{frame} Thinking...")
            self._spinner_frame += 1
        except Exception:
            pass

    def _stop_thinking_spinner(self) -> None:
        """Remove the spinner when AI starts responding."""
        try:
            if hasattr(self, "_spinner_timer") and self._spinner_timer:
                self._spinner_timer.stop()
                self._spinner_timer = None
            if hasattr(self, "_spinner_label") and self._spinner_label:
                self._spinner_label.remove()
                self._spinner_label = None
        except Exception:
            pass

    def _handle_slash_command(self, cmd: str) -> None:
        parts = cmd.split()
        base = parts[0].lower()
        logger.debug(f"Handling slash command: {base}")

        from src.core.commands import CommandRegistry

        registry = CommandRegistry()
        if registry.execute(base):
            return

        if base == "/setup":
            self.app.action_push_onboarding()
        else:
            self._append_message(
                "system",
                f"Unknown command: {base}. Type /help or use the Command Palette (Ctrl+Shift+P).",
            )

    def _append_message(
        self, role: str, content: str, name: str = "", time_str: str = ""
    ) -> ChatMessage:
        try:
            existing = self.query_one("#transient-status")
            existing.remove()
        except Exception as e:
            logger.debug(f"Transient remove failed: {e}")

        msg = ChatMessage(role=role, content=content, name=name, time_str=time_str)
        is_at_bottom = self.scroll_container.scroll_y >= self.scroll_container.max_scroll_y
        self.scroll_container.mount(msg)
        if is_at_bottom:
            self.scroll_container.scroll_end(animate=False)
        return msg

    def on_mouse_down(self, event: MouseDown) -> None:
        if event.button == 3:
            from src.tui.widgets.context_menu import ContextMenuSpawner
            from src.tui.widgets.menu import MenuItem

            items = [
                MenuItem("Copy Chat as Markdown", action="chat_copy_md"),
                MenuItem("Export Session...", action="chat_export"),
                MenuItem(is_separator=True),
                MenuItem("Clear Chat", action="chat.clear"),
                MenuItem(is_separator=True),
                MenuItem("Pin Session", action="chat_pin_session"),
            ]
            ContextMenuSpawner.spawn(self.app, event, items)
            event.stop()

    @on(OrchestratorNarration)
    def handle_narration(self, event: OrchestratorNarration) -> None:
        colors = {
            "info": "dim white",
            "decision": "bold cyan",
            "routing": "bold blue",
            "result": "bold green",
            "error": "bold red",
        }
        color = colors.get(event.narration_type, "white")
        from datetime import datetime

        time_str = datetime.now().strftime("%I:%M %p")
        self._append_message(
            "system", f"[{color}]⚙️ {event.text}[/{color}]", "Orchestrator", time_str
        )
        self.scroll_container.scroll_end(animate=False)

    @on(AgentStatusUpdate)
    def on_agent_status_update(self, event: AgentStatusUpdate) -> None:
        """Handle transient AI status states like Orchestrator thinking or Reflection logic."""
        if event.status == "thinking":
            # Stop the thinking spinner now that we have a real agent status
            self._stop_thinking_spinner()
            from textual.widgets import Label
            # Remove any existing transient
            try:
                existing = self.query_one("#transient-status")
                existing.remove()
            except Exception as e:
                logger.debug(f"Transient status remove failed: {e}")

            model_display = f"({event.model_name})" if event.model_name else ""
            status_pill = Label(f"🧠 [bold #58A6FF]{event.agent_id.capitalize()} {model_display} {event.status}...[/] [dim]{event.detail}[/]", id="transient-status", classes="transient-pill")  # noqa: E501
            status_pill.styles.margin = (0, 0, 1, 0)
            self.scroll_container.mount(status_pill)
            self.scroll_container.scroll_end(animate=False)
        elif event.status == "completed":
            try:
                existing = self.query_one("#transient-status")
                existing.remove()
            except Exception as e:
                logger.debug(f"Transient status cleanup failed: {e}")

    @on(ParallelDispatchStarted)
    def on_parallel_dispatch_started(self, event: ParallelDispatchStarted) -> None:
        # Stop the thinking spinner — AI has started responding
        self._stop_thinking_spinner()
        from datetime import datetime

        time_str = datetime.now().strftime("%I:%M %p")
        # Announce the start
        mode_str = event.mode.capitalize()
        self._append_message(
            "system",
            f"🚀 Starting {mode_str} Mode across {len(event.agents)} agents...",
            "Orchestrator",
            time_str,
        )

        # Create container for parallel streams
        container = Horizontal(id=f"dispatch-{event.dispatch_id}")
        container.styles.height = "auto"
        container.styles.margin = (1, 0)

        self.scroll_container.mount(container)
        self._parallel_containers[event.dispatch_id] = container
        self._agent_boxes[event.dispatch_id] = {}

        # Add streaming boxes for each agent
        for agent_info in event.agents:
            box = AgentStreamBox(
                agent_id=agent_info["agent_id"],
                model_name=agent_info["model_name"],
                emoji=agent_info.get("emoji", "🤖"),
                color=agent_info.get("color", "white"),
            )
            container.mount(box)
            self._agent_boxes[event.dispatch_id][agent_info["agent_id"]] = box

        self.scroll_container.scroll_end(animate=False)

    @on(MultiAgentChunk)
    def on_multi_agent_chunk(self, event: MultiAgentChunk) -> None:
        boxes = self._agent_boxes.get(event.dispatch_id, {})
        box = boxes.get(event.agent_id)
        if box:
            box.append_chunk(event.text)

    @on(MultiAgentToolCall)
    def on_multi_agent_tool_call(self, event: MultiAgentToolCall) -> None:
        boxes = self._agent_boxes.get(event.dispatch_id, {})
        box = boxes.get(event.agent_id)
        if box:
            box.add_tool_call(event.tool_name, event.args)

    @on(ParallelAgentComplete)
    def on_parallel_agent_complete(self, event: ParallelAgentComplete) -> None:
        boxes = self._agent_boxes.get(event.dispatch_id, {})
        box = boxes.get(event.agent_id)
        if box:
            result = event.result
            if "error" in result and result["error"]:
                box.mark_error(result["error"])
            else:
                box.mark_complete(result.get("duration_ms", 0), result.get("cost_usd", 0.0))

    @on(ParallelDispatchComplete)
    def on_parallel_dispatch_complete(self, event: ParallelDispatchComplete) -> None:
        self._append_message(
            "system", "🏁 Parallel generation complete. Evaluating patches...", "Orchestrator"
        )

    @on(ArbiterVerdictReady)
    def on_arbiter_verdict_ready(self, event: ArbiterVerdictReady) -> None:
        """Handle arbiter verdicts and mount ArbiterVerdictPanel."""
        logger.info("Chat received pending patchset and arbiter verdict.")
        if event.verdict:
            from src.core.mode_manager import OperationMode

            is_architect = False
            if hasattr(self.app, "orchestrator") and self.app.orchestrator:
                is_architect = (
                    self.app.orchestrator.mode_manager.active_mode == OperationMode.ARCHITECT
                )

            if is_architect:
                from src.tui.widgets.architect_approval_panel import ArchitectApprovalPanel

                panel = ArchitectApprovalPanel(event.verdict)
            else:
                from src.tui.widgets.arbiter_verdict_panel import ArbiterVerdictPanel

                panel = ArbiterVerdictPanel(event.verdict)

            self.scroll_container.mount(panel)
            self.scroll_container.scroll_end(animate=False)

    @on(ContextModified)
    def on_context_modified(self, event: ContextModified) -> None:
        """Handle when context chips are modified."""
        logger.debug(f"Context modified: {event.action} for {event.file_path}")

    @on(ContextTruncated)
    def on_context_truncated(self, event: ContextTruncated) -> None:
        """Surface a visible warning when the context manager drops messages or truncates files."""
        from datetime import datetime
        time_str = datetime.now().strftime("%I:%M %p")

        detail_parts = [f"[bold #F59E0B]⚠ Context Limit:[/] {event.reason}"]
        if event.files_truncated:
            file_list = ", ".join(event.files_truncated)
            detail_parts.append(f"[dim]Truncated files: {file_list}[/dim]")
        if event.tokens_dropped > 0:
            detail_parts.append(f"[dim](~{event.tokens_dropped:,} tokens removed)[/dim]")

        self._append_message("system", "\n".join(detail_parts), "Context Manager", time_str)
        self.scroll_container.scroll_end(animate=False)

    @on(ReflectionRetryHint)
    def on_reflection_retry_hint(self, event: ReflectionRetryHint) -> None:
        """Surface a lesson from the reflection engine and store it for the next dispatch."""
        from datetime import datetime

        from textual.widgets import Collapsible
        time_str = datetime.now().strftime("%I:%M %p")

        # Store the lesson so the next task dispatch can inject it as a system hint
        self._pending_reflection_hint = event.lesson

        # Mount a collapsible so users can read the full lesson
        coll = Collapsible(
            Label(event.lesson),
            title=f"🧠 Memory Updated ({event.model_name}) — {time_str}",
            collapsed=True,
        )
        coll.styles.width = "100%"
        coll.styles.color = "#818CF8"
        self.scroll_container.mount(coll)
        self.scroll_container.scroll_end(animate=False)
