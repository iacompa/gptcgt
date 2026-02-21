"""Main App Shell for gptcgt."""

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static
from textual.binding import Binding

from src.core.workspace import Workspace
from src.core.chat_store import ChatStore
from src.core.events import FileSelected
from src.tui.panels.file_tree import FileTreePanel
from src.tui.panels.activity_feed import ActivityFeedPanel
from src.tui.panels.chat import ChatPanel
from src.tui.overlays.session_browser import SessionBrowser

class CodeViewerPanelPlaceholder(Static):
    """Placeholder for CodeViewerPanel."""
    DEFAULT_CSS = """
    CodeViewerPanelPlaceholder {
        border-right: solid #30363D;
    }
    """

class GptcgtApp(App[None]):
    """Main application shell for gptcgt."""

    CSS_PATH = ["themes/midnight.tcss"]
    
    BINDINGS = [
        Binding("ctrl+b", "toggle_left_panel", "Toggle File Tree"),
        Binding("ctrl+j", "toggle_right_panel", "Toggle Chat"),
        Binding("ctrl+shift+z", "toggle_zen_mode", "Zen Mode"),
        Binding("ctrl+t", "toggle_theme", "Toggle Theme"),
        Binding("ctrl+p", "fuzzy_search", "Fuzzy Search"),
        Binding("ctrl+h", "session_history", "Session History"),
        Binding("tab", "app.focus_next", "Focus Next", show=False),
        Binding("shift+tab", "app.focus_previous", "Focus Previous", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.current_theme = "midnight"

    def compose(self) -> ComposeResult:
        # Temporary instantiation to provide store to ChatPanel before fully initializing in on_mount
        # In a real async Textual app setup, you might do this via reactive bindings, but passing 
        # it in is fine for this architecture.
        ws = Workspace(os.getcwd())
        self.chat_store = ChatStore(ws)
        self.chat_store.load_active_session()

        with Horizontal(id="app-grid"):
            yield FileTreePanel(id="left-panel")
            yield ChatPanel(self.chat_store, id="center-panel")
            yield ActivityFeedPanel(id="right-panel")
        
        # Add session indicator label
        self.session_indicator = Static("Session: 0 messages │ 0.0K tokens | Started --:--", id="session-indicator")
        
        status_bar = Horizontal(id="status-bar")
        with status_bar:
            yield Static("Press Ctrl+B to toggle tree, Ctrl+T for theme, Ctrl+Shift+Z for zen, Ctrl+H for history")
            yield self.session_indicator

    def on_mount(self) -> None:
        """Initialize workspace and chat history on mount."""
        self._update_session_indicator()

    def _update_session_indicator(self) -> None:
        if not hasattr(self, 'session_indicator'): return
        msgs = self.chat_store._cache
        if not msgs: return
        start_time = msgs[0].timestamp.strftime("%H:%M %p")
        text = f"Session: {len(msgs)} messages │ Started {start_time}"
        self.session_indicator.update(text)

    def on_file_selected(self, message: FileSelected) -> None:
        """Handle file selection."""
        self.log(f"File selected: {message.filepath}")

    def action_toggle_left_panel(self) -> None:
        """Toggle left panel visibility."""
        panel = self.query_one("#left-panel")
        panel.display = not panel.display

    def action_toggle_right_panel(self) -> None:
        """Toggle right panel visibility."""
        panel = self.query_one("#right-panel")
        panel.display = not panel.display

    def action_toggle_zen_mode(self) -> None:
        """Hide both side panels."""
        left = self.query_one("#left-panel")
        right = self.query_one("#right-panel")
        zen_active = not (left.display or right.display)
        if zen_active:
            left.display = True
            right.display = True
        else:
            left.display = False
            right.display = False

    def action_toggle_theme(self) -> None:
        """Cycle through themes (midnight -> polar -> slate -> ember -> neon -> midnight)."""
        import os
        from textual.css.stylesheet import Stylesheet
        
        themes = ["midnight", "polar", "slate", "ember", "neon"]
        try:
            current_index = themes.index(self.current_theme)
        except ValueError:
            current_index = 0
            
        next_index = (current_index + 1) % len(themes)
        self.current_theme = themes[next_index]
        self.log(f"Switching theme to {self.current_theme}")
        
        theme_path = os.path.join(os.path.dirname(__file__), "themes", f"{self.current_theme}.tcss")
            
        # Nasty trick to dynamically load CSS in 0.50 if stylesheet API differs:
        try:
            with open(theme_path, "r") as f:
                css_content = f.read()
                self.stylesheet.source = css_content
                self.stylesheet.update()
                self.refresh(layout=True)
                
                # Update status bar to indicate theme change
                status_bar_msg = f"Theme: {self.current_theme} | Press Ctrl+B to toggle tree, Ctrl+T for theme, Ctrl+Shift+Z for zen"
                status_bar = self.query_one("#status-bar")
                status_bar.update(status_bar_msg)
        except Exception as e:
            self.log(f"Error loading theme {self.current_theme}: {e}")

    def action_fuzzy_search(self) -> None:
        """Placeholder for fuzzy search."""
        self.log("fuzzy search")

    def action_session_history(self) -> None:
        """Push the SessionBrowser modal."""
        def check_session_switch(new_session_id: str | None) -> None:
            if new_session_id:
                # Reload UI components
                chat_panel = self.query_one("#center-panel", ChatPanel)
                chat_panel.query("ChatMessageContainer").remove()
                chat_panel.on_mount()
                self._update_session_indicator()

        self.push_screen(SessionBrowser(self.chat_store), check_session_switch)

def main() -> None:
    """Entry point for the application."""
    app = GptcgtApp()
    app.run()

if __name__ == "__main__":
    main()
