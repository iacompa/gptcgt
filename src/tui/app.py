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
from src.core.quality_tiers import QualityTierManager, QualityTier
from src.billing.cost_breakdown import CostBreakdownTracker
from src.billing.overage import OverageManager
from src.core.task_tracker import TaskTracker
from src.tui.widgets.status_bar import EnhancedStatusBar
from src.tui.widgets.task_panel import TaskPanel
from src.tui.overlays.tier_selector import TierSelectorOverlay

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
        Binding("ctrl+q", "tier_selector", "Tier Selector"),
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
            with Vertical(id="left-panel-container", classes="left-col"):
                yield TaskPanel(id="task-panel")
                yield FileTreePanel(id="left-panel")
            yield ChatPanel(self.chat_store, id="center-panel")
            yield ActivityFeedPanel(id="right-panel")
        
        # Enhanced status bar handles session/cost info internally via reactives
        self.status_bar = EnhancedStatusBar(id="status-bar")
        yield self.status_bar

    def on_mount(self) -> None:
        """Initialize workspace and chat history on mount."""
        self.tier_manager = QualityTierManager()
        self.cost_tracker = CostBreakdownTracker()
        self.overage_manager = OverageManager()
        self.task_tracker = TaskTracker()
        
        # Link UI components to managers
        task_panel = self.query_one("#task-panel", TaskPanel)
        task_panel.tracker = self.task_tracker
        
        self._update_status_bar()

    def _update_status_bar(self) -> None:
        """Sync manager states to the Enhanced StatusBar."""
        if not hasattr(self, 'status_bar'): return
        
        tier_cfg = self.tier_manager.config
        self.status_bar.tier_icon = tier_cfg.icon
        self.status_bar.tier_name = tier_cfg.display_name
        self.status_bar.tier_color = tier_cfg.color
        
        today = self.cost_tracker.get_today_spend()
        self.status_bar.today_cost = today.total_cost
        self.status_bar.month_cost = self.cost_tracker.get_monthly_spend()
        
        overage = self.overage_manager.state
        self.status_bar.is_overage = overage.is_in_overage
        self.status_bar.credits_remaining = overage.remaining_credits
        self.status_bar.plan_credits = overage.plan_credits
        if overage.plan_credits > 0:
            self.status_bar.budget_pct = min(1.0, overage.used_credits / overage.plan_credits)

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

    def action_tier_selector(self) -> None:
        """Push the TierSelector modal."""
        def check_tier_switch(new_tier: QualityTier | None) -> None:
            if new_tier:
                self.tier_manager.set_tier(new_tier)
                self._update_status_bar()

        self.push_screen(TierSelectorOverlay(self.tier_manager.active_tier), check_tier_switch)

def main() -> None:
    """Entry point for the application."""
    app = GptcgtApp()
    app.run()

if __name__ == "__main__":
    main()
