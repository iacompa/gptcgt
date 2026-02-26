"""Main App Shell for gptcgt."""

from __future__ import annotations

import sys
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical

from src.billing.cost_breakdown import CostBreakdownTracker
from src.billing.overage import OverageManager
from src.core.chat_store import ChatStore
from src.core.commands import register_default_commands
from src.core.config import ConfigManager
from src.core.events import FileSelected, PatchSetProposed, TaskReceived
from src.core.logger import get_logger, setup_logging
from src.core.quality_tiers import QualityTier, QualityTierManager
from src.core.task_tracker import TaskTracker
from src.core.workspace import Workspace

# Panels needed at compose() time — must be eager
from src.tui.panels.chat import ChatPanel
from src.tui.panels.code_viewer import CodeViewerPanel
from src.tui.panels.file_tree import FileTreePanel
from src.tui.panels.leaderboard import LeaderboardPanel
from src.tui.widgets.menu import MenuAction, MenuToggle
from src.tui.widgets.menu_bar import MenuBar
from src.tui.widgets.panel_resizer import PanelResizer
from src.tui.widgets.status_bar import EnhancedStatusBar
from src.tui.widgets.task_panel import TaskPanel

# Overlays are lazy-loaded inside each action method (never needed at startup)

logger = get_logger("tui.app")


class GptcgtApp(App[None]):
    """Main application shell for gptcgt."""

    CSS_PATH = ["themes/midnight.tcss"]
    CSS = """
    Screen {
        scrollbar-size: 1 1;
        scrollbar-background: transparent;
        scrollbar-color: $surface-light;
        scrollbar-color-hover: $primary-muted;
        scrollbar-color-active: $primary;
    }
    """

    BINDINGS = [
        Binding("ctrl+b", "toggle_left_panel", "Toggle File Tree"),
        Binding("ctrl+j", "toggle_right_panel", "Toggle Chat"),
        Binding("ctrl+shift+z", "toggle_zen_mode", "Zen Mode"),
        Binding("ctrl+t", "toggle_theme", "Toggle Theme"),
        Binding("ctrl+p", "fuzzy_search", "Fuzzy Search"),
        Binding("ctrl+shift+p", "command_palette", "Command Palette"),
        Binding("ctrl+h", "session_history", "Session History"),
        Binding("ctrl+q", "tier_selector", "Tier Selector"),
        Binding("ctrl+m", "mode_picker", "Mode Picker"),
        Binding("ctrl+comma", "show_settings", "Settings"),
        Binding("ctrl+question_mark", "show_help", "Help"),
        Binding("ctrl+l", "toggle_leaderboard", "Leaderboard"),
        Binding("ctrl+space", "toggle_quick_actions", "Quick Actions", show=True),
        Binding("f1", "show_help", "Help", show=False),
        Binding("tab", "app.focus_next", "Focus Next", show=False),
        Binding("shift+tab", "app.focus_previous", "Focus Previous", show=False),
        Binding("escape", "stop_generation", "Stop Run", show=True),
    ]

    def action_stop_generation(self) -> None:
        """Cancel the currently running agent task."""
        if hasattr(self, "cancel_event") and self.cancel_event is not None:
            self.cancel_event.set()
            from src.tui.widgets.toast import notify

            notify(self, "Stopped", "Halting AI generation...", "warning")

    def action_mode_picker(self) -> None:
        """Open the mode picker overlay (Ctrl+M)."""
        from src.tui.overlays.mode_picker import ModePickerOverlay

        current = (
            self.orchestrator.mode_manager.active_mode
            if hasattr(self, "orchestrator")
            else None
        )
        from src.core.mode_manager import OperationMode
        current = current or OperationMode.STANDARD

        def _apply_mode(chosen_mode: OperationMode | None) -> None:
            if not chosen_mode:
                return
            self.orchestrator.mode_manager.set_mode(chosen_mode)
            from src.tui.widgets.toast import notify
            notify(self, "Mode Changed", f"Switched to {chosen_mode.name} mode.", "info")
            self._update_status_bar()

        self.push_screen(ModePickerOverlay(current_mode=current), _apply_mode)

    def action_toggle_leaderboard(self) -> None:
        """Toggles the global ELO Leaderboard view."""
        try:
            panel = self.query_one("#leaderboard", expect_type=LeaderboardPanel)
            panel.toggle_visibility()
        except Exception as e:
            logger.error(f"Failed to toggle leaderboard: {e}")

    def __init__(self) -> None:
        super().__init__()
        self._active_theme_name = "midnight"
        self.project_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()

    def compose(self) -> ComposeResult:
        # Temporary instantiation to provide store to ChatPanel
        try:
            ws = Workspace.get_instance()
        except Exception:
            ws = Workspace(self.project_path)

        self.chat_store = ChatStore(ws)
        self.chat_store.load_active_session()

        from src.core.model_registry import ModelRegistry
        from src.core.orchestrator import Orchestrator

        # Load model catalog from bundled JSON BEFORE creating the pipeline
        ModelRegistry().load()

        self.orchestrator = Orchestrator(self.chat_store)

        yield MenuBar()
        with Horizontal(id="app-grid"):
            # Construct the 3 main clusters
            panels = {
                "files": Vertical(TaskPanel(id="task-panel"), FileTreePanel(id="left-panel"), id="left-panel-container", classes="left-col"),  # noqa: E501
                "code": CodeViewerPanel(id="code-viewer"),
                "chat": ChatPanel(id="right-panel")
            }

            # Fetch the sequence string parsing
            from src.core.config import ConfigManager
            _conf = getattr(self, "config", ConfigManager())
            order = getattr(_conf.user, "layout_order", "files_code_chat").split("_")
            if len(order) != 3 or not all(k in panels for k in order):
                order = ["files", "code", "chat"]

            # Yield components linked with Resizers dynamically
            yield panels[order[0]]
            yield PanelResizer(panels[order[0]].id, panels[order[1]].id, id="resizer-1")
            yield panels[order[1]]
            yield PanelResizer(panels[order[1]].id, panels[order[2]].id, id="resizer-2")
            yield panels[order[2]]

        from src.tui.widgets.toast import ToastContainer
        yield ToastContainer()

        yield LeaderboardPanel(id="leaderboard")

        from src.tui.widgets.quick_actions import QuickActionsBar

        self.quick_actions = QuickActionsBar(id="quick-actions")
        yield self.quick_actions

        # Enhanced status bar handles session/cost info internally via reactives
        self.status_bar = EnhancedStatusBar(id="status-bar")
        yield self.status_bar

    def watch_theme(self, new_theme: str) -> None:
        """Triggered automatically when self.theme changes, allowing dynamic UI repaints."""
        try:
            from src.tui.panels.chat import ChatPanel

            chat_panel = self.query(ChatPanel).first()
            if hasattr(chat_panel, "input_area"):
                chat_panel.input_area.theme = "github_light" if new_theme == "polar" else "vscode_dark"
        except Exception:
            pass

        try:
            from src.tui.panels.code_viewer import CodeView

            for cv in self.query(CodeView):
                # Only re-render if it holds active content
                if cv.content or cv.patch:
                    cv._update_display()
        except Exception:
            pass

        try:
            from src.tui.widgets.hunk_editor import HunkEditor
            for he in self.query(HunkEditor):
                he.text_area.theme = "github_light" if new_theme == "polar" else "vscode_dark"
        except Exception:
            pass

    async def _init_openrouter_models(self, active_models: list[str]) -> None:
        """Fetch pricing and definitions for user-saved OpenRouter models."""
        try:
            from src.core.model_registry import ModelRegistry, QualityTier
            registry = ModelRegistry()
            data = await registry.fetch_openrouter_models()
            for model_id in active_models:
                registry.register_custom_openrouter_model(
                    model_id, "", QualityTier.STANDARD, openrouter_data=data
                )
            logger.info(f"Loaded {len(active_models)} custom OpenRouter models from config.")
        except Exception as e:
            logger.warning(f"Failed to init background OpenRouter models: {e}")

    async def on_ready(self) -> None:
        """Initialize workspace and chat history on ready."""
        try:
            # 0. Setup structured logging
            debug_mode = getattr(self, "debug_mode", False)
            setup_logging(self.project_path, debug=debug_mode)
            logger.info(f"App mounted with project path: {self.project_path}")

            # 0.5 Ensure all state managers exist BEFORE anything else
            ws = Workspace.get_instance()
            from src.core.phase_tracker import PhaseTracker
            self.phase_tracker = PhaseTracker(ws)
            self.phase_tracker.ensure_loaded()

            self.config = ConfigManager()
            self.config.auto_detect_project()

            from src.auth.auth_manager import AuthManager
            self.auth_manager = AuthManager()
            # Validate stored token in background — catches expired/revoked tokens
            # without blocking UI startup. LogsOut user on confirmed 401.
            self.call_after_refresh(
                lambda: self.run_worker(
                    self.auth_manager.validate_token_on_startup(),
                    name="token_validation",
                    exclusive=False,
                )
            )

            # Load stored OpenRouter custom models asynchronously
            def _load_openrouter_models():
                try:
                    active_ors = getattr(self.config.user, "openrouter_active_models", [])
                    if active_ors:
                        self.run_worker(self._init_openrouter_models(active_ors), exclusive=False)
                except Exception:
                    pass
            self.call_after_refresh(_load_openrouter_models)

            self._register_themes()
            self._active_theme_name = self.config.user.theme
            self.theme = self._active_theme_name
            self.tier_manager = QualityTierManager()
            tier_map = {
                "light": QualityTier.LIGHT,
                "standard": QualityTier.STANDARD,
                "max": QualityTier.MAX,
            }
            self.tier_manager.set_tier(
                tier_map.get(self.config.user.default_quality_tier, QualityTier.STANDARD)
            )

            self.cost_tracker = CostBreakdownTracker()
            if hasattr(self, "chat_pipeline"):
                self.chat_pipeline.cost_tracker = self.cost_tracker
            self.overage_manager = OverageManager()
            self.task_tracker = TaskTracker()

            # Link UI components to managers
            task_panel = self.query_one("#task-panel", TaskPanel)
            task_panel.tracker = self.task_tracker

            # Register central commands early
            register_default_commands(self)
            self._update_status_bar()

            # 1. Validate path (exit immediately if invalid — no modal)
            from src.core.init import ProjectInitializer

            initializer = ProjectInitializer(self.project_path)
            validation = initializer.validate_project_path(self.project_path)

            if not validation["valid"]:
                logger.error(f"Invalid project path: {validation['errors']}")
                self.exit(message=f"Invalid path: {', '.join(validation['errors'])}")
                return

            # 2. Auto-initialize project silently if needed (no modal)
            if not initializer.is_initialized():
                logger.info("Auto-initializing project (first run)...")
                initializer.initialize_project()

            # 3. Creator Mode for empty projects
            def is_project_empty() -> bool:
                count = 0
                try:
                    for entry in self.project_path.iterdir():
                        if entry.name != ".gptcgt" and entry.name != ".git":
                            count += 1
                            if count > 0:
                                return False
                    return True
                except Exception:
                    return False

            if is_project_empty():
                logger.info("Project directory is empty. Initializing Creator Mode layout.")
                from src.core.mode_manager import OperationMode
                self.apply_layout("chat_focus")
                self.orchestrator.mode_manager.set_mode(OperationMode.ARCHITECT)

            # 4. Crash Recovery — auto-clear stale state (no modal)
            from src.core.crash_recovery import CrashRecoveryManager
            recovery = CrashRecoveryManager(self.project_path)
            if recovery.check_for_crash():
                logger.warning("Unclean shutdown detected — auto-clearing stale state.")
                recovery.clear_state()

            # Acquire lock for this session
            recovery.acquire_lock()
            self._recovery_mgr = recovery

            # 5. Onboarding — non-blocking push (no await)
            if not self.config.user.setup_completed:
                self.action_push_onboarding()

            from src.services.analytics import track
            uid = (
                getattr(self, "auth_manager", None)
                and getattr(self.auth_manager, "_profile", {})
                and self.auth_manager._profile.get("id")
                or "anonymous"
            )
            import platform
            track(uid, "app_launched", {"version": "1.0", "platform": platform.platform()})

            # 6. Setup Crash Recovery Auto-Save Timer
            self.set_interval(10.0, self._auto_save)

            logger.info("App ready — all systems initialized.")

        except Exception as e:
            logger.error(f"Fatal error during app initialization: {e}", exc_info=True)
            import traceback
            err_path = self.project_path / ".gptcgt" / "startup_error.log"
            err_path.parent.mkdir(parents=True, exist_ok=True)
            err_path.write_text(traceback.format_exc())
            self.exit(message=f"Startup error: {e}. See {err_path}")

    def _auto_save(self) -> None:
        """Triggered periodically to save state."""
        if hasattr(self, "_recovery_mgr") and hasattr(self, "task_tracker"):
            from src.core.crash_recovery import RecoverableState

            # Simple state extraction for now
            active_task = "None"
            _task = self.task_tracker.get_active_task()
            if _task:
                active_task = _task.title

            state = RecoverableState(active_task=active_task, progress=0)
            self._recovery_mgr.save_state(state)

    def _update_status_bar(self) -> None:
        """Sync manager states to the Enhanced StatusBar."""
        if not hasattr(self, "status_bar"):
            return

        tier_cfg = self.tier_manager.config
        self.status_bar.tier_icon = tier_cfg.icon
        self.status_bar.tier_name = tier_cfg.display_name
        self.status_bar.tier_color = tier_cfg.color

        today = self.cost_tracker.get_today_spend()
        self.status_bar.today_cost = today.total_cost
        self.status_bar.month_cost = self.cost_tracker.get_monthly_spend()

        overage = self.overage_manager.state
        self.status_bar.is_overage = overage.is_in_overage
        if (
            hasattr(self, "auth_manager")
            and self.auth_manager.is_authenticated
            and self.auth_manager.use_managed_credits
        ):
            self.status_bar.credits_remaining = self.auth_manager.credits_remaining
            self.status_bar.plan_credits = self.auth_manager.credits_monthly
            if self.status_bar.plan_credits > 0:
                used = self.status_bar.plan_credits - self.status_bar.credits_remaining
                self.status_bar.budget_pct = min(1.0, max(0.0, used / self.status_bar.plan_credits))
        else:
            self.status_bar.credits_remaining = overage.remaining_credits
            self.status_bar.plan_credits = overage.plan_credits
            if overage.plan_credits > 0:
                self.status_bar.budget_pct = min(1.0, overage.used_credits / overage.plan_credits)

    async def on_file_selected(self, message: FileSelected) -> None:
        """Handle file selection."""
        logger.debug(f"File selected via event: {message.filepath}")
        viewer = self.query_one("#code-viewer", CodeViewerPanel)
        try:
            content = message.filepath.read_text(encoding="utf-8")
            viewer.show_file(message.filepath, content)

            # Phase 10: Graceful UI Pane Restore from chat_focus
            if not viewer.display:
                self.apply_layout("default")

            if hasattr(self, "quick_actions"):
                self.quick_actions.context = {
                    "target": "file",
                    "file_path": str(message.filepath),
                }
        except Exception as e:
            logger.error(f"Failed to read file for viewer: {e}")

    @on(PatchSetProposed)
    def handle_patch_proposed(self, event: PatchSetProposed) -> None:
        viewer = self.query_one(CodeViewerPanel)

        # Phase 10: Graceful UI Pane Restore from chat_focus mode
        if not viewer.display:
            self.apply_layout("default")
            from src.tui.widgets.toast import notify

            notify(self, "Creator Mode", "Switching to IDE layout to show code changes.", "info")

        from src.core.diff_engine import MultiAgentPatchSet

        if isinstance(event.patch_set, MultiAgentPatchSet):
            viewer.load_multi_patch_set(event.patch_set)
        else:
            viewer.load_patch_set(event.patch_set)

    @work(exclusive=True)
    async def process_task(self, task_str: str, attached_files: list) -> None:
        from src.core.model_registry import ModelRegistry
        from src.core.model_registry import QualityTier as RegistryQualityTier
        from src.core.quality_tiers import QualityTier as AppQualityTier
        from src.tui.panels.chat import ChatPanel

        chat_panel = self.query_one("#right-panel", ChatPanel)

        # Resolve model info for event posting
        registry = ModelRegistry()
        app_tier = (
            self.tier_manager.active_tier
            if hasattr(self, "tier_manager")
            else AppQualityTier.STANDARD
        )
        registry_tier = RegistryQualityTier(app_tier.value)
        model_def = registry.get_default_for_tier(registry_tier)
        model_id = model_def.id if model_def else "unknown"
        model_name = model_def.name if model_def else "AI"

        # Create agent message bubble to stream into
        agent_msg = chat_panel._append_message("agent", "", model_name, "")

        async def yield_chunk(chunk: str):
            agent_msg.append_chunk(chunk)

        async def tool_call(msg: str, args: dict):
            from src.tui.widgets.toast import notify

            notify(self, "Tool Action", msg, "info")

        async def thought_call(title: str, content: str):
            import asyncio

            from src.tui.panels.chat import apply_brand_colors

            while not agent_msg.is_mounted:
                await asyncio.sleep(0.05)

            # Grab current speaker string (e.g. "Orchestrator (openai/gpt-4o)")
            # and strip out just the literal model to pass down to CSS styling.
            active_model_str = agent_msg.speaker_name
            colored_title = apply_brand_colors(f"{active_model_str} {title}")
            agent_msg.append_thought(colored_title, content)

        async def cmd_error(msg: str):
            import asyncio
            # Wait for Textual to mount the message bubble
            while not agent_msg.is_mounted:
                await asyncio.sleep(0.05)

            agent_msg.append_chunk(f"\n[Error: {msg}]")
            from src.tui.widgets.toast import notify
            notify(self, "LLM Error", msg, "error")

        file_dicts = []
        try:
            from src.core.workspace import Workspace, WorkspaceEscapeError
            ws = Workspace.get_instance()
        except Exception:
            ws = None

        for f in attached_files:
            try:
                if ws:
                    try:
                        ws.validate_path(str(f))
                    except WorkspaceEscapeError:
                        logger.warning(f"Attached file rejected (outside workspace): {f}")
                        continue
                    content = ws.safe_read(str(f))
                else:
                    content = f.read_text()
                file_dicts.append({"path": str(f), "content": content})
            except Exception as e:
                logger.error(f"Failed to read attached file {f}: {e}")

        # Phase 11: Setup Panic Button Cancellation Event
        import asyncio

        self.cancel_event = asyncio.Event()

        # Set status bar to running state
        self.status_bar.is_running = True

        from src.core.events import AgentCompleted, AgentDispatched, OrchestratorNarration

        async def _narration(txt: str, typ: str):
            self.post_message(OrchestratorNarration(txt, typ))

        async def on_model_selected(real_model_name: str):
            agent_msg.update_speaker(f"Orchestrator ({real_model_name})")
            self.post_message(AgentDispatched(agent_name="Orchestrator", model_name=real_model_name))

        from src.services.analytics import track

        uid = (
            getattr(self, "auth_manager", None)
            and getattr(self.auth_manager, "_profile", {})
            and self.auth_manager._profile.get("id")
            or "anonymous"
        )
        track(uid, "task_submitted", {"mode": "standard", "tier": registry_tier.name})

        import time

        start_time = time.monotonic()
        try:
            await self.orchestrator.process_task(
                user_input=task_str,
                attached_files=file_dicts,
                global_tier=registry_tier,
                narration_callback=_narration,
                yield_chunk_callback=yield_chunk,
                tool_call_callback=tool_call,
                thought_callback=thought_call,
                error_callback=cmd_error,
                model_selected_callback=on_model_selected,
                cancel_event=self.cancel_event,
            )
        except asyncio.CancelledError:
            agent_msg.append_chunk("\n\n[Generation Stopped by User]")
            logger.info("Task generation was cancelled by user.")
        finally:
            self.cancel_event = None
            agent_msg.finalize_streaming()
            dur_ms = int((time.monotonic() - start_time) * 1000)
            track(uid, "task_completed", {"mode": "standard", "duration_ms": dur_ms, "credits": 5})
            self.post_message(AgentCompleted(agent_id=model_id, full_response=agent_msg.content))
            self.status_bar.is_running = False
            self._update_status_bar()

    async def on_task_received(self, message: TaskReceived) -> None:
        logger.info(f"Task received event: {message.task_str}")
        self.process_task(message.task_str, message.attached_files)

    def action_push_onboarding(self) -> None:
        """Push the onboarding overlay."""
        from src.tui.overlays.onboarding import OnboardingScreen
        self.push_screen(OnboardingScreen())

    def action_show_settings(self) -> None:
        """Push the settings overlay."""
        from src.tui.overlays.settings import SettingsScreen
        self.push_screen(SettingsScreen())

    def action_show_help(self) -> None:
        """Push the help overlay."""
        from src.tui.overlays.help import HelpOverlay
        self.push_screen(HelpOverlay())

    def on_menu_action(self, event: MenuAction) -> None:
        """Handle actions emitted from the dropdown menu."""
        from src.core.commands import CommandRegistry

        logger.debug(f"Menu action received: {event.action}")
        if CommandRegistry().execute(event.action):
            return

        action = event.action

        # Legacy map for not-yet-migrated actions
        if action == "about":
            # Show a brief about toast instead of silent no-op
            from src.tui.widgets.toast import notify
            notify(self, "About gptcgt", "Version 0.1.0 — gptcgt.ai", "info")
        elif action == "continue_session":
            # Reload last session
            if hasattr(self, "chat_store"):
                self.chat_store.load_active_session()
                notify(self, "Session", "Loaded last session.", "subtle")
        elif action == "export_chat":
            # Export to clipboard / file
            try:
                chat_panel = self.query_one("#right-panel", ChatPanel)
                lines = []
                for child in chat_panel.scroll_container.children:
                    if hasattr(child, "content") and child.content:
                        role = getattr(child, "role", "system")
                        lines.append(f"**{role.capitalize()}**: {child.content}")
                md = "\n\n".join(lines)
                import pyperclip
                pyperclip.copy(md)
                notify(self, "Exported", "Chat copied to clipboard as Markdown.", "success")
            except Exception as e:
                logger.debug(f"Export chat failed: {e}")
                notify(self, "Export", "Could not export chat (pyperclip not installed).", "warning")
        elif action == "clear_chat":
            self.action_clear_chat()
            notify(self, "Cleared", "Chat history cleared.", "subtle")
        elif action == "check_updates":
            import webbrowser
            webbrowser.open("https://github.com/your/repo/releases")
        elif action == "mode_picker":
            self.action_mode_picker()
        elif action == "push_onboarding":
            self.action_push_onboarding()
        elif action in ("show_settings_keys", "app.settings"):
            from src.tui.overlays.settings import SettingsScreen
            self.push_screen(SettingsScreen())
        elif action == "toggle_left_panel":
            self.action_toggle_left_panel()
        elif action == "toggle_right_panel":
            self.action_toggle_right_panel()
        elif action == "toggle_zen_mode":
            self.action_toggle_zen_mode()
        elif action == "layout_default":
            self.apply_layout("default")
        elif action == "layout_code_focus":
            self.apply_layout("code_focus")
        elif action == "layout_review":
            self.apply_layout("review")
        elif action == "layout_chat_focus":
            self.apply_layout("chat_focus")
        elif action == "show_layout_editor":
            self.action_show_layout_editor()
        elif action == "size_default":
            self.apply_size("default")
        elif action == "size_wide_code":
            self.apply_size("wide_code")
        elif action == "size_wide_chat":
            self.apply_size("wide_chat")
        elif action == "size_equal":
            self.apply_size("equal")
        elif action.startswith("theme_"):
            theme_name = action.split("_", 1)[1]
            self._apply_theme(theme_name)
        elif action.startswith("tier_"):
            tier_name = action.split("_")[1].upper()
            try:
                tier = QualityTier[tier_name]
                self.tier_manager.set_tier(tier)
                self._update_status_bar()
            except KeyError:
                pass
        elif action.startswith("mode_"):
            mode_name = action.split("_")[1].upper()
            try:
                from src.core.mode_manager import OperationMode

                mode = OperationMode[mode_name]
                self.orchestrator.mode_manager.set_mode(mode)
                from src.tui.widgets.toast import notify

                self.call_after_refresh(
                    notify, self, "Mode Changed", f"Switched to {mode.name} mode.", "info"
                )
            except KeyError:
                pass
        elif action == "show_billing":
            from src.tui.overlays.settings import SettingsScreen
            self.push_screen(SettingsScreen())  # Specific tab later
        elif action == "show_help":
            self.action_show_help()
        elif action == "open_docs":
            import webbrowser

            webbrowser.open("https://docs.gptcgt.ai")
        elif action == "open_guide":
            import webbrowser

            webbrowser.open("https://gptcgt.ai/guide")
        elif action == "open_issues":
            import webbrowser

            webbrowser.open("https://github.com/your/repo/issues")
        elif action.startswith("ai_") or action.startswith("tree_"):
            # Route file tree AI context-menu actions
            try:
                from src.tui.panels.file_tree import FileTreePanel
                file_tree = self.query_one(FileTreePanel)
                file_tree._handle_ai_tree_action(action)
            except Exception as e:
                logger.debug(f"AI tree action failed: {e}")

    def on_menu_toggle(self, event: MenuToggle) -> None:
        """Handle toggles in menu."""
        logger.debug(f"Menu toggled: {event.label} -> {event.new_state}")

    def action_clear_chat(self) -> None:
        """Clear the chat panel."""
        chat_panel = self.query_one("#right-panel", ChatPanel)
        for child in chat_panel.scroll_container.children:
            child.remove()
        logger.info("Chat cleared")

    async def on_unmount(self) -> None:
        """Clean up resources on exit."""
        if hasattr(self, "_recovery_mgr"):
            self._recovery_mgr.clear_state()
            logger.debug("Cleaned up recovery state on unmount.")

    def _get_active_layout_order(self) -> list[str]:
        order = getattr(self.config.user, "layout_order", "files_code_chat").split("_")
        if len(order) != 3 or not all(k in ["files", "code", "chat"] for k in order):
            order = ["files", "code", "chat"]
        return order

    def action_toggle_left_panel(self) -> None:
        """Toggle the leftmost panel (dynamically evaluated via settings)."""
        order = self._get_active_layout_order()
        panel_map = {"files": "#left-panel-container", "code": "#code-viewer", "chat": "#right-panel"}
        leftmost = self.query_one(panel_map[order[0]])
        resizer = self.query_one("#resizer-1")
        leftmost.display = not leftmost.display
        resizer.display = leftmost.display

    def action_toggle_right_panel(self) -> None:
        """Toggle the rightmost panel (dynamically evaluated via settings)."""
        order = self._get_active_layout_order()
        panel_map = {"files": "#left-panel-container", "code": "#code-viewer", "chat": "#right-panel"}
        rightmost = self.query_one(panel_map[order[2]])
        resizer = self.query_one("#resizer-2")
        rightmost.display = not rightmost.display
        resizer.display = rightmost.display

    def action_toggle_zen_mode(self) -> None:
        """Hide both side panels."""
        order = self._get_active_layout_order()
        panel_map = {"files": "#left-panel-container", "code": "#code-viewer", "chat": "#right-panel"}
        left = self.query_one(panel_map[order[0]])
        right = self.query_one(panel_map[order[2]])

        left_r = self.query_one("#resizer-1")
        right_r = self.query_one("#resizer-2")
        zen_active = not (left.display or right.display)

        left.display = zen_active
        left_r.display = zen_active
        right.display = zen_active
        right_r.display = zen_active

    def on_panel_resizer_reset_layout(self, event: PanelResizer.ResetLayout) -> None:
        """Double click on resizer resetting to default."""
        order = self._get_active_layout_order()
        panel_map = {"files": "#left-panel-container", "code": "#code-viewer", "chat": "#right-panel"}
        left = self.query_one(panel_map[order[0]])
        center = self.query_one(panel_map[order[1]])
        right = self.query_one(panel_map[order[2]])

        # We restore normal FR weights
        left.styles.width = "20%"
        center.styles.width = "1fr"
        right.styles.width = "30%"

    def on_panel_resizer_resize_complete(self, event: PanelResizer.ResizeComplete) -> None:
        """Fired after drag completes, so we can save new widths to ConfigManager later."""
        pass

    def action_show_layout_editor(self) -> None:
        from src.tui.overlays.layout_editor import LayoutEditorOverlay

        def check_layout(layout_name: str | None) -> None:
            if layout_name:
                self.apply_layout(layout_name)

        self.push_screen(LayoutEditorOverlay(), check_layout)

    def apply_layout(self, preset: str) -> None:
        order = self._get_active_layout_order()
        panel_map = {"files": "#left-panel-container", "code": "#code-viewer", "chat": "#right-panel"}
        left = self.query_one(panel_map[order[0]])
        center = self.query_one(panel_map[order[1]])
        right = self.query_one(panel_map[order[2]])
        left_r = self.query_one("#resizer-1")
        right_r = self.query_one("#resizer-2")

        if preset == "default":
            left.display, center.display, right.display = True, True, True
            left_r.display, right_r.display = True, True
        elif preset == "code_focus":
            left.display, center.display, right.display = False, True, True
            left_r.display, right_r.display = False, True
        elif preset == "review":
            left.display, center.display, right.display = True, True, False
            left_r.display, right_r.display = True, False
        elif preset == "chat_focus":
            left.display, center.display, right.display = False, False, True
            left_r.display, right_r.display = False, False

    def apply_size(self, preset: str) -> None:
        left = self.query_one("#left-panel-container")
        center = self.query_one("#code-viewer")
        right = self.query_one("#right-panel")

        if preset == "default":
            left.styles.width, center.styles.width, right.styles.width = "20%", "1fr", "30%"
        elif preset == "wide_code":
            left.styles.width, center.styles.width, right.styles.width = "15%", "1fr", "25%"
        elif preset == "wide_chat":
            left.styles.width, center.styles.width, right.styles.width = "15%", "1fr", "45%"
        elif preset == "equal":
            left.styles.width, center.styles.width, right.styles.width = "33%", "1fr", "33%"

    def action_toggle_theme(self) -> None:
        """Cycle through themes (midnight -> polar -> slate -> ember -> neon -> midnight)."""
        themes = ["midnight", "polar", "slate", "ember", "neon"]
        try:
            current_index = themes.index(self._active_theme_name)
        except ValueError:
            current_index = 0

        next_index = (current_index + 1) % len(themes)
        self._apply_theme(themes[next_index])

    def _register_themes(self) -> None:
        """Register native Textual Themes to replace dynamic CSS injection."""
        from textual.theme import Theme

        self.register_theme(Theme(
            name="midnight",
            background="#0D1117",
            panel="#161B22",
            surface="#1C2333",
            secondary="#30363D",
            primary="#58A6FF",
            success="#3FB950",
            warning="#D29922",
            error="#F85149",
            dark=True
        ))
        self.register_theme(Theme(
            name="polar",
            background="#FFFFFF",
            panel="#F6F8FA",
            surface="#EAEEF2",
            secondary="#D0D7DE",
            primary="#0969DA",
            success="#1A7F37",
            warning="#9A6700",
            error="#CF222E",
            dark=False
        ))
        self.register_theme(Theme(
            name="slate",
            background="#1A1C29",
            panel="#222536",
            surface="#2B2E42",
            secondary="#44415C",
            primary="#7E56C2",
            success="#3BA772",
            warning="#E5A93B",
            error="#DE4F55",
            dark=True
        ))
        self.register_theme(Theme(
            name="ember",
            background="#211A1A",
            panel="#2C2222",
            surface="#3A2D2B",
            secondary="#3E2723",
            primary="#FF5722",
            success="#388E3C",
            warning="#FFC107",
            error="#D32F2F",
            dark=True
        ))
        self.register_theme(Theme(
            name="neon",
            background="#0A0A0A",
            panel="#141414",
            surface="#1F1F1F",
            secondary="#330033",
            primary="#FF00FF",
            success="#00FF00",
            warning="#FFFF00",
            error="#FF0000",
            dark=True
        ))

    def _apply_theme(self, theme_name: str) -> None:
        """Apply a registered textual theme by name."""
        self._active_theme_name = theme_name
        logger.debug(f"Switching theme to {self._active_theme_name}")

        self.theme = theme_name

        # Update status bar
        try:
            status_bar_msg = f"Theme: {theme_name} | Ctrl+T to cycle themes"
            status_bar = self.query_one("#status-bar")
            status_bar.update(status_bar_msg)
        except Exception:
            pass

    def action_command_palette(self) -> None:
        """Push the command palette overlay."""
        from src.tui.overlays.command_palette import CommandPaletteScreen

        logger.debug("Opening Command Palette")
        self.push_screen(CommandPaletteScreen())

    def action_fuzzy_search(self) -> None:
        """Placeholder for fuzzy search."""
        logger.debug("fuzzy search")

    def action_session_history(self) -> None:
        """Push the SessionBrowser modal."""
        from src.tui.overlays.session_browser import SessionBrowser

        def check_session_switch(new_session_id: str | None) -> None:
            if new_session_id:
                chat_panel = self.query_one("#right-panel", ChatPanel)
                chat_panel._load_session_history()
                self._update_status_bar()

        self.push_screen(SessionBrowser(self.chat_store), check_session_switch)

    def action_tier_selector(self) -> None:
        """Push the TierSelector modal."""
        from src.tui.overlays.tier_selector import TierSelectorOverlay

        def check_tier_switch(new_tier: QualityTier | None) -> None:
            if new_tier:
                self.tier_manager.set_tier(new_tier)
                self._update_status_bar()

        self.push_screen(TierSelectorOverlay(self.tier_manager.active_tier), check_tier_switch)

    def action_show_status(self) -> None:
        """Check provider connectivity and display status."""
        self.run_worker(self._check_provider_status())

    async def _check_provider_status(self) -> None:
        from src.agents.health import check_all_providers

        chat_panel = self.query_one("ChatPanel")
        chat_panel._append_message("system", "Checking provider status...")

        results = await check_all_providers()
        lines = ["**Provider Status:**"]
        for r in results:
            icon = "✅" if r.reachable else "❌"
            latency = f" ({r.latency_ms}ms)" if r.latency_ms else ""
            error = f" — {r.error}" if r.error else ""
            lines.append(f"  {icon} {r.provider}{latency}{error}")

        chat_panel._append_message("system", "\n".join(lines))

    def action_show_version(self) -> None:
        from importlib.metadata import version as get_version

        try:
            v = get_version("gptcgt")
        except Exception:
            v = "dev"
        from src.tui.widgets.toast import notify

        notify(self, "Version", f"gptcgt {v}", "info")

    def action_login(self) -> None:
        """Start WorkOS device flow authentication."""
        self.run_worker(self._start_login_flow())

    async def _start_login_flow(self) -> None:
        from src.tui.widgets.toast import notify

        if not hasattr(self, "auth_manager") or self.auth_manager is None:
            from src.auth.auth_manager import AuthManager

            self.auth_manager = AuthManager()

        if self.auth_manager.is_authenticated:
            notify(
                self,
                "Already Signed In",
                f"Signed in as {self.auth_manager._profile.get('email', 'unknown')}",
                "info",
            )
            return

        try:
            chat_panel = self.query_one("ChatPanel")
            flow = await self.auth_manager.start_device_flow()
            code = flow.get("user_code", "???")
            uri = flow.get("verification_uri", "https://gptcgt.ai/auth")
            chat_panel._append_message(
                "system",
                f"**Sign In**\nGo to: {uri}\nEnter code: **{code}**\n\nWaiting for authorization...",  # noqa: E501
            )

            device_code = flow.get("device_code")
            success = await self.auth_manager.poll_device_flow(device_code)

            if success:
                email = (
                    self.auth_manager._profile.get("email", "your account")
                    if self.auth_manager._profile
                    else "your account"
                )
                notify(self, "Signed In", f"Welcome, {email}!", "success")
                self._update_status_bar()
            else:
                notify(
                    self, "Sign In Failed", "Authorization timed out. Try /login again.", "error"
                )
        except Exception as e:
            notify(self, "Sign In Error", str(e)[:100], "error")

    def action_logout(self) -> None:
        if hasattr(self, "auth_manager") and self.auth_manager:
            self.auth_manager.logout()
            self._update_status_bar()
            from src.tui.widgets.toast import notify

            notify(self, "Signed Out", "You have been signed out. Using BYOK mode.", "info")
        else:
            from src.tui.widgets.toast import notify

            notify(self, "Not Signed In", "You are not currently signed in.", "warning")

    def action_show_credits(self) -> None:
        from src.tui.widgets.toast import notify

        if (
            hasattr(self, "auth_manager")
            and self.auth_manager
            and self.auth_manager.is_authenticated
        ):
            remaining = self.auth_manager.credits_remaining
            monthly = self.auth_manager.credits_monthly
            plan = self.auth_manager.user_plan
            notify(
                self,
                "Credits",
                f"{remaining:,}/{monthly:,} credits remaining | Plan: {plan.upper()}",
                "info",
            )
        else:
            notify(
                self, "Credits", "BYOK mode — no managed credits. Use /login to sign in.", "info"
            )

    def action_show_billing(self) -> None:
        from src.tui.widgets.toast import notify

        notify(
            self,
            "Billing",
            "Visit gptcgt.ai/dashboard/billing to manage your subscription.",
            "info",
        )

    def action_toggle_quick_actions(self) -> None:
        """Toggle visibility of the quick actions bar."""
        if hasattr(self, "quick_actions"):
            self.quick_actions.toggle_visibility()

    from src.core.events import (
        AnnotationActionClicked,
        CodeSelectionCleared,
        CodeSelectionMade,
        FileRelevanceUpdated,
        QuickActionTriggered,
    )

    @on(CodeSelectionMade)
    def on_code_selection_for_actions(self, event: CodeSelectionMade) -> None:
        """Update quick actions context when code is selected."""
        if hasattr(self, "quick_actions"):
            self.quick_actions.context = {
                "target": "selection",
                "file_path": event.file_path,
                "start_line": event.start_line,
                "end_line": event.end_line,
                "content": event.content,
            }
            if not self.quick_actions.has_class("visible"):
                self.quick_actions.add_class("visible")
            # Forward to context chips
            try:
                from src.tui.widgets.context_chips import ContextChipBar

                chip_bar = self.query_one(ContextChipBar)
                chip_bar.add_selection_chip(event.file_path, event.start_line, event.end_line)
            except Exception:
                pass

    @on(CodeSelectionCleared)
    def on_code_selection_cleared_for_actions(self, event: CodeSelectionCleared) -> None:
        """Revert to default or file context when selection is cleared."""
        if hasattr(self, "quick_actions"):
            try:
                viewer = self.query(CodeViewerPanel).first()
                code_view = viewer.query_one("#code-view") if viewer else None
                if code_view and hasattr(code_view, "filepath") and code_view.filepath:
                    self.quick_actions.context = {
                        "target": "file",
                        "file_path": str(code_view.filepath),
                    }
                else:
                    self.quick_actions.context = None
            except Exception:
                self.quick_actions.context = None

    @on(FileRelevanceUpdated)
    def on_file_relevance_for_chips(self, event: FileRelevanceUpdated) -> None:
        """Forward file relevance updates to context chips."""
        try:
            from src.tui.widgets.context_chips import ContextChipBar

            chip_bar = self.query_one(ContextChipBar)
            for f in event.files:
                chip_bar.add_file_chip(f)
        except Exception:
            pass

    @on(QuickActionTriggered)
    def on_quick_action(self, event: QuickActionTriggered) -> None:
        """Execute the chosen quick action by generating a task prompt."""
        action = event.action
        context = event.context

        prompt = ""
        files = []

        from src.tui.panels.chat import ChatPanel

        if context.get("target") == "selection":
            file_name = Path(context["file_path"]).name
            start = context["start_line"]
            end = context["end_line"]
            files.append(Path(context["file_path"]))

            if action == "explain_selection":
                prompt = f"Explain the code selection in {file_name} (lines {start}-{end})."
            elif action == "find_bugs_selection":
                prompt = f"Find any bugs or issues in the code selection in {file_name} (lines {start}-{end})."  # noqa: E501
            elif action == "refactor_selection":
                prompt = f"Refactor the code selection in {file_name} (lines {start}-{end}) to improve it."  # noqa: E501
            elif action == "write_tests_selection":
                prompt = (
                    f"Write unit tests for the code selection in {file_name} (lines {start}-{end})."
                )

        elif context.get("target") == "file":
            file_name = Path(context["file_path"]).name
            files.append(Path(context["file_path"]))

            if action == "explain_file":
                prompt = f"Explain the purpose and structure of {file_name}."
            elif action == "find_bugs_file":
                prompt = f"Find bugs or code smells in {file_name}."
            elif action == "refactor_file":
                prompt = f"Refactor {file_name} to improve code quality."
            elif action == "write_tests_file":
                prompt = f"Write unit tests for {file_name}."

        else:
            if action == "explain_project":
                prompt = "Give me an overview of this project's architecture."
            elif action == "find_bugs":
                prompt = "Analyze the project for potential bugs or security issues."

        if prompt:
            self.post_message(TaskReceived(task_str=prompt, attached_files=files))
            try:
                chat_panel = self.query_one("#right-panel", ChatPanel)
                self.set_focus(chat_panel.input_area)
            except Exception as e:
                logger.error(f"Failed to focus chat panel: {e}")

    @on(AnnotationActionClicked)
    def on_annotation_action(self, event: AnnotationActionClicked) -> None:
        """Handle annotation fix actions by creating a task."""
        action = event.action
        file_path = event.file_path
        line = event.line_number
        message = event.context.get("message", "")
        severity = event.context.get("severity", "info")

        if action == "fix":
            prompt = f"Fix the {severity} issue at line {line} in {Path(file_path).name}: {message}"
        elif action == "ignore":
            # Just dismiss the annotation panel — no task needed
            return
        else:
            prompt = f"Address the annotation at line {line} in {Path(file_path).name}: {message}"

        if prompt:
            files = [Path(file_path)] if file_path else []
            self.post_message(TaskReceived(task_str=prompt, attached_files=files))


def main() -> None:
    """Entry point for the application."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-V"):
        from importlib.metadata import version

        try:
            v = version("gptcgt")
        except Exception:
            v = "dev"
        print(f"gptcgt {v}")
        sys.exit(0)

    debug_mode = "--debug" in sys.argv

    app = GptcgtApp()
    app.debug_mode = debug_mode
    app.run()


if __name__ == "__main__":
    main()
