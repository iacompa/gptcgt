"""Session Browser Overlay for persistent chat history."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView

from src.core.chat_store import ChatStore


class SessionItem(ListItem):
    """A list item representing a chat session."""

    def __init__(self, session_data: dict, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.session_data = session_data

    def compose(self) -> ComposeResult:
        import datetime

        dt = datetime.datetime.fromtimestamp(self.session_data["date"])
        date_str = dt.strftime("%Y-%m-%d %H:%M")

        yield Horizontal(
            Label(
                f"{date_str} ({self.session_data['message_count']} msgs)", classes="session-date"
            ),
            Label(self.session_data["preview"], classes="session-preview"),
        )


class SessionBrowser(ModalScreen):
    """Modal overlay to browse past chat sessions."""

    DEFAULT_CSS = """
    SessionBrowser {
        align: center middle;
        background: $background 80%;
    }
    #browser-dialog {
        width: 80%;
        height: 80%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    .browser-title {
        text-style: bold;
        margin-bottom: 1;
        color: $text;
    }
    #session-list {
        height: 1fr;
        margin-top: 1;
        margin-bottom: 1;
        background: $panel;
    }
    .session-date {
        width: 30%;
        color: $primary;
    }
    .session-preview {
        width: 70%;
        color: $text-muted;
    }
    .browser-buttons {
        height: auto;
        align: right middle;
    }
    """

    def __init__(self, chat_store: ChatStore, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.chat_store = chat_store

    def compose(self) -> ComposeResult:
        with Vertical(id="browser-dialog"):
            yield Label("Session History", classes="browser-title")
            yield Input(placeholder="Search across all sessions...", id="session-search")
            yield ListView(id="session-list")

            with Horizontal(classes="browser-buttons"):
                yield Button("Load Session", id="btn-load", variant="primary", disabled=True)
                yield Button("Export to Markdown", id="btn-export", disabled=True)
                yield Button("Delete", id="btn-delete", variant="error", disabled=True)
                yield Button("Close", id="btn-close")

    def on_mount(self) -> None:
        self._load_sessions()

    def _load_sessions(self, search_query: str = "") -> None:
        list_view = self.query_one("#session-list", ListView)
        list_view.clear()

        if not search_query:
            sessions = self.chat_store.list_sessions()
            for s in sessions:
                list_view.append(SessionItem(s))
        else:
            results = self.chat_store.search_sessions(search_query)
            # Group by session ID to avoid duplicates in view
            seen = set()
            for s_id, msg in results:
                if s_id in seen:
                    continue
                seen.add(s_id)
                # mock session data for view
                stat = self.chat_store._get_session_path(s_id).stat()
                list_view.append(
                    SessionItem(
                        {
                            "id": s_id,
                            "date": stat.st_mtime,
                            "message_count": "?",  # don't calculate just for search view
                            "preview": f"...{msg.content[:50]}...",
                        }
                    )
                )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "session-search":
            self._load_sessions(event.value)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        has_selection = event.item is not None
        self.query_one("#btn-load", Button).disabled = not has_selection
        self.query_one("#btn-export", Button).disabled = not has_selection
        self.query_one("#btn-delete", Button).disabled = not has_selection

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss()

        list_view = self.query_one("#session-list", ListView)
        selected = list_view.highlighted_child
        if not selected or not isinstance(selected, SessionItem):
            return

        session_id = selected.session_data["id"]

        if event.button.id == "btn-load":
            # Just switching current session
            self.chat_store.current_session_id = session_id
            self.chat_store._cache = self.chat_store._load_from_disk(
                self.chat_store._get_session_path(session_id)
            )
            self.chat_store._update_current_symlink(self.chat_store._get_session_path(session_id))
            self.dismiss(session_id)

        elif event.button.id == "btn-export":
            md = self.chat_store.export_session(session_id)
            export_path = self.chat_store.workspace.get_project_root() / f"export_{session_id}.md"
            self.chat_store.workspace.safe_write(export_path, md)
            self.app.notify(f"Exported to {export_path.name}")

        elif event.button.id == "btn-delete":
            self.chat_store.delete_session(session_id)
            self.app.notify("Session deleted")
            self._load_sessions(self.query_one("#session-search", Input).value)
