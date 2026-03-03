"""
Code viewer panel for displaying file contents and diffs.
In diff mode, shows red/green backgrounds and provides
approve/reject/apply logic for PatchSets.
"""

from __future__ import annotations

from pathlib import Path

from pygments import highlight
from pygments.lexers import TextLexer, get_lexer_for_filename
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Resize
from textual.reactive import reactive
from textual.widgets import Button, Label, Static

from src.core.diff_engine import FilePatch, MultiAgentPatchSet, PatchEngine, PatchSet
from src.core.logger import get_logger
from src.tui.widgets.code_selector import CodeLineClicked, CodeLineWidget, SelectionManager
from src.tui.widgets.syntax_colors import build_terminal_formatter

logger = get_logger("tui.code_viewer")


class SmoothScroll(VerticalScroll):
    """VerticalScroll with controlled 3-line wheel increments (no jitter)."""

    def _on_mouse_scroll_down(self, event) -> None:
        event.prevent_default()
        event.stop()
        self.scroll_relative(y=3, animate=False)

    def _on_mouse_scroll_up(self, event) -> None:
        event.prevent_default()
        event.stop()
        self.scroll_relative(y=-3, animate=False)



class CodeView(Vertical):
    """Displays syntax-highlighted code with per-line selection support, or unified diffs."""

    DEFAULT_CSS = """
    CodeView {
        width: 100%;
        height: 1fr;
    }
    #code-lines-scroll {
        height: 1fr;
        width: 100%;
        overflow-x: auto;
        overflow-y: auto;
        scrollbar-size: 1 1;
    }
    #code-diff-view {
        width: 100%;
        height: 1fr;
        overflow-x: auto;
        overflow-y: auto;
        scrollbar-size: 1 1;
    }
    #selection-indicator {
        dock: top;
        height: 1;
        background: $primary;
        text-style: bold;
        color: $text;
        text-align: center;
        display: none;
    }
    """

    content = reactive("")
    filepath = reactive("")
    is_diff = reactive(False)
    patch = reactive(None)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        from src.tui.widgets.annotations import AnnotationManager

        self.selection_manager = SelectionManager()
        self.annotation_manager = AnnotationManager()
        self._line_widgets: list[CodeLineWidget] = []
        self._raw_lines: list[str] = []

    def refresh_annotations(self) -> None:
        """Update annotation markers on all visible code lines."""
        for w in self._line_widgets:
            ann = self.annotation_manager.get_annotation(w.line_number)
            w.set_annotation(ann)

    def compose(self) -> ComposeResult:
        yield Static("", id="selection-indicator", classes="selection-mode-indicator")
        yield SmoothScroll(id="code-lines-scroll")
        yield Static("", id="code-diff-view")

    def on_mount(self) -> None:
        """Hide diff view by default."""
        self.query_one("#code-diff-view").display = False

    def watch_content(self, content: str) -> None:
        self._update_display()

    def watch_filepath(self, filepath: str) -> None:
        self._update_display()

    def watch_is_diff(self, is_diff: bool) -> None:
        self._update_display()

    def watch_patch(self, patch: FilePatch | None) -> None:
        self._update_display()

    def _update_display(self) -> None:
        """Render code as per-line widgets or diff as monolithic text."""
        # Clear any active selection
        self.selection_manager.clear()
        self._update_selection_indicator()

        if not self.content and not self.patch:
            self._show_placeholder("No file selected.")
            return

        if self.is_diff and self.patch:
            self._show_diff_mode()
            return

        self._show_code_mode()

    def _show_placeholder(self, text: str) -> None:
        """Show a placeholder message."""
        scroll = self.query_one("#code-lines-scroll", VerticalScroll)
        diff_view = self.query_one("#code-diff-view", Static)
        scroll.display = True
        diff_view.display = False
        # Remove old line widgets
        for w in list(scroll.children):
            w.remove()
        self._line_widgets = []
        self._raw_lines = []
        scroll.mount(Static(text))

    def _show_diff_mode(self) -> None:
        """Render diff as monolithic text (no per-line selection in diff mode)."""
        scroll = self.query_one("#code-lines-scroll", VerticalScroll)
        diff_view = self.query_one("#code-diff-view", Static)
        scroll.display = False
        diff_view.display = True
        diff_view.update(self._render_diff())

    def _show_code_mode(self) -> None:
        """Render code as individual CodeLineWidget instances."""
        scroll = self.query_one("#code-lines-scroll", VerticalScroll)
        diff_view = self.query_one("#code-diff-view", Static)
        scroll.display = True
        diff_view.display = False

        # Remove old widgets
        for w in list(scroll.children):
            w.remove()
        self._line_widgets = []

        # Syntax highlight
        try:
            lexer = get_lexer_for_filename(self.filepath)
        except Exception:
            lexer = TextLexer()

        formatter = build_terminal_formatter(getattr(self.app, "theme", "midnight"))
        highlighted = highlight(self.content, lexer, formatter)

        raw_lines = self.content.splitlines()
        highlighted_lines = highlighted.splitlines()
        self._raw_lines = raw_lines

        # Pad highlighted_lines if it has fewer lines than raw
        while len(highlighted_lines) < len(raw_lines):
            highlighted_lines.append("")

        # Keep line-number gutter tight for small files while preserving alignment.
        line_digits = max(2, len(str(len(raw_lines) if raw_lines else 1)))

        # Create per-line widgets
        for i, (raw, hl) in enumerate(zip(raw_lines, highlighted_lines), 1):
            widget = CodeLineWidget(
                line_number=i,
                content=raw,
                highlighted_content=hl,
                annotation=self.annotation_manager.get_annotation(i),
                line_number_digits=line_digits,
                classes="code-line",
            )
            self._line_widgets.append(widget)
            scroll.mount(widget)

    def _render_diff(self) -> str:
        """Render diff view (unchanged from existing implementation)."""
        if not self.patch:
            return ""
        lines = [f"[bold white]Diff for {self.patch.file_path}[/bold white]\n"]
        for i, hunk in enumerate(self.patch.hunks):
            if hasattr(hunk, "user_edited") and hunk.user_edited and hunk.user_text is not None:
                status_color = "cyan"
                lines.append(
                    f"[{status_color}]@@ -{hunk.start_line} +{hunk.end_line} @@ (USER EDITED)[/{status_color}]"  # noqa: E501
                )
                for ln in hunk.original_lines:
                    lines.append(f"[red on #330000]- {ln}[/red on #330000]")
                for ln in hunk.user_text.splitlines():
                    lines.append(f"[cyan on #003333]+ {ln}[/cyan on #003333]")
            else:
                status_color = {"pending": "yellow", "approved": "green", "rejected": "red"}.get(
                    hunk.status, "white"
                )
                lines.append(
                    f"[{status_color}]@@ -{hunk.start_line} +{hunk.end_line} @@ ({hunk.status.upper()})[/{status_color}]"  # noqa: E501
                )
                for ln in hunk.original_lines:
                    lines.append(f"[red on #330000]- {ln}[/red on #330000]")
                for ln in hunk.modified_lines:
                    lines.append(f"[green on #003300]+ {ln}[/green on #003300]")
            lines.append("")
        return "\n".join(lines)

    # --- Selection Methods ---

    def enter_selection_mode(self) -> None:
        """Enter selection mode starting at the first visible line or line 1."""
        if not self._line_widgets:
            return
        # Default to line 1
        self.selection_manager.start_selection(1)
        self._refresh_selection_visuals()
        self._update_selection_indicator()

    def exit_selection_mode(self) -> None:
        """Exit selection mode and clear all highlights."""
        self.selection_manager.clear()
        self._refresh_selection_visuals()
        self._update_selection_indicator()
        from src.core.events import CodeSelectionCleared

        self.post_message(CodeSelectionCleared())

    def confirm_selection(self) -> None:
        """Confirm selection and emit CodeSelectionMade event."""
        rng = self.selection_manager.get_range()
        if rng is None:
            return
        start, end = rng
        # Extract raw content for the selected range
        selected_lines = self._raw_lines[start - 1 : end]
        content = "\n".join(selected_lines)

        from src.core.events import CodeSelectionMade

        self.post_message(
            CodeSelectionMade(
                file_path=self.filepath,
                start_line=start,
                end_line=end,
                content=content,
            )
        )
        # Exit selection mode after confirming
        self.selection_manager.clear()
        self._refresh_selection_visuals()
        self._update_selection_indicator()

    def extend_selection_down(self) -> None:
        """Extend selection one line down."""
        if not self.selection_manager.is_active:
            return
        self.selection_manager.move_cursor_down(len(self._line_widgets))
        self._refresh_selection_visuals()
        self._update_selection_indicator()
        self._scroll_to_cursor()

    def extend_selection_up(self) -> None:
        """Extend selection one line up."""
        if not self.selection_manager.is_active:
            return
        self.selection_manager.move_cursor_up()
        self._refresh_selection_visuals()
        self._update_selection_indicator()
        self._scroll_to_cursor()

    def handle_line_clicked(self, line_number: int, shift_held: bool) -> None:
        """Handle a click on a specific line number."""
        if shift_held and self.selection_manager.is_active:
            # Extend selection to clicked line
            self.selection_manager.extend_selection(line_number)
        else:
            # Start new selection at clicked line
            self.selection_manager.start_selection(line_number)
        self._refresh_selection_visuals()
        self._update_selection_indicator()

    def _refresh_selection_visuals(self) -> None:
        """Update is_selected on all line widgets to match SelectionManager state."""
        for widget in self._line_widgets:
            widget.is_selected = self.selection_manager.is_line_selected(widget.line_number)

    def _update_selection_indicator(self) -> None:
        """Update the selection mode indicator bar."""
        indicator = self.query_one("#selection-indicator", Static)
        if self.selection_manager.is_active:
            rng = self.selection_manager.get_range()
            if rng:
                start, end = rng
                count = end - start + 1
                indicator.update(
                    f"SELECTION MODE | Lines {start}-{end} ({count} lines) | Enter=Confirm | Esc=Cancel | j/k=Extend"  # noqa: E501
                )
            else:
                indicator.update("SELECTION MODE | v=Start | Click a line | Esc=Cancel")
            indicator.display = True
        else:
            indicator.display = False

    def _scroll_to_cursor(self) -> None:
        """Scroll the code view to keep the cursor visible."""
        cursor = self.selection_manager.cursor
        if cursor is None or cursor < 1 or cursor > len(self._line_widgets):
            return
        widget = self._line_widgets[cursor - 1]
        widget.scroll_visible()


class CodeViewerPanel(Vertical):
    """Container for the code view map and diff controls."""

    DEFAULT_CSS = """
    CodeViewerPanel {
        width: 100%;
        height: 100%;
    }
    #code-file-header {
        width: 100%;
        background: $surface;
        color: $primary;
        text-style: bold;
        padding: 0 1;
        border-bottom: solid $secondary;
        height: auto;
    }
    .hidden {
        display: none;
    }
    #code-action-bar {
        display: none;
        height: 1;
        padding: 0;
        background: $surface;
        width: 100%;
        layout: horizontal;
        align: left middle;
    }
    .action-group {
        width: auto;
        height: 1;
        padding: 0;
        margin: 0;
        layout: horizontal;
    }
    #multi-agent-controls {
        margin-right: 1;
    }
    .action-label {
        width: auto;
        content-align: left middle;
        text-style: bold;
        color: $primary;
        margin: 0 1 0 0;
        height: 1;
    }
    .button-row {
        height: 1;
        width: auto;
        layout: horizontal;
        align: left middle;
    }
    .button-row Button {
        min-width: 3;
        width: auto;
        height: 1;
        margin: 0 0 0 0;
        padding: 0 1;
        content-align: center middle;
        border: none;
    }
    #multi-agent-controls .button-row Button {
        max-width: 12;
    }
    #diff-controls .button-row Button {
        width: auto;
    }
    """

    BINDINGS = [
        Binding("g", "toggle_annotations", "Toggle Annotations", show=True),
        Binding("v", "enter_selection", "Select Lines", show=False),
        Binding("e", "edit_hunk", "Edit Hunk", show=True),
        Binding("j", "extend_down", "Extend Down", show=False),
        Binding("k", "extend_up", "Extend Up", show=False),
        Binding("down", "extend_down", "Extend Down", show=False),
        Binding("up", "extend_up", "Extend Up", show=False),
        Binding("enter", "confirm_selection", "Confirm Selection", show=False),
        Binding("escape", "cancel_selection", "Cancel Selection", show=False, priority=True),
    ]

    patch_set: PatchSet | None = None
    multi_patch_set: MultiAgentPatchSet | None = None
    agent_idx: int = 0
    current_patch_idx: int = 0
    current_hunk_idx: int = 0

    def compose(self) -> ComposeResult:
        yield Label("No file selected", id="code-file-header")
        with Horizontal(id="code-action-bar"):
            with Vertical(classes="action-group", id="multi-agent-controls"):
                yield Label("Agent 1/2", id="multi-agent-label", classes="action-label")
                with Horizontal(classes="button-row"):
                    btn_prev_a = Button("◀ Previous", id="btn-prev-agent", variant="primary")
                    btn_prev_a.tooltip = "View previous agent's proposal"
                    yield btn_prev_a

                    btn_next_a = Button("Next ▶", id="btn-next-agent", variant="primary")
                    btn_next_a.tooltip = "View next agent's proposal"
                    yield btn_next_a

            with Vertical(classes="action-group", id="diff-controls"):
                yield Label("Review Hunks", id="diff-label", classes="action-label")
                with Horizontal(classes="button-row"):
                    btn_prev_h = Button("◀", id="btn-prev-hunk", variant="primary")
                    btn_prev_h.tooltip = "Previous Hunk"
                    yield btn_prev_h

                    btn_approve = Button("✓", id="btn-approve", variant="success")
                    btn_approve.tooltip = "Approve this hunk for merging"
                    yield btn_approve

                    btn_reject = Button("✗", id="btn-reject", variant="error")
                    btn_reject.tooltip = "Reject this hunk"
                    yield btn_reject

                    btn_next_h = Button("▶", id="btn-next-hunk", variant="primary")
                    btn_next_h.tooltip = "Next Hunk"
                    yield btn_next_h

                    btn_apply = Button("Apply", id="btn-apply-all", variant="warning")
                    btn_apply.tooltip = "Write all currently approved hunks to disk"
                    yield btn_apply
        yield CodeView(id="code-view")

    def on_resize(self, event: Resize) -> None:
        """Dynamically toggle between verbose text and compact symbols based on panel width."""
        width = event.size.width

        # We consider < 65 as 'compact' mode, requiring symbols over words
        is_compact = width < 65

        try:
            b_prev_a = self.query_one("#btn-prev-agent", Button)
            b_next_a = self.query_one("#btn-next-agent", Button)
            b_prev_h = self.query_one("#btn-prev-hunk", Button)
            b_approve = self.query_one("#btn-approve", Button)
            b_reject = self.query_one("#btn-reject", Button)
            b_next_h = self.query_one("#btn-next-hunk", Button)
            b_apply = self.query_one("#btn-apply-all", Button)

            b_prev_a.label = "◀" if is_compact else "◀ Prev"
            b_next_a.label = "▶" if is_compact else "Next ▶"

            # Remove symbols when not compact to match user's prior memory
            b_prev_h.label = "◀" if is_compact else "◀ Prev"
            b_approve.label = "✓" if is_compact else "Approve"
            b_reject.label = "✗" if is_compact else "Reject"
            b_next_h.label = "▶" if is_compact else "Next ▶"
            b_apply.label = "All" if is_compact else "Apply All"
        except Exception as e:
            logger.debug(f"Button label compact update failed: {e}")

    def show_file(self, path: Path, content: str) -> None:
        self.patch_set = None
        self.multi_patch_set = None

        header = self.query_one("#code-file-header", Label)
        header.update(f"📄 {path.name}  [dim]({path})[/dim]")

        # Hide action bar when browsing files (no diff)
        self.query_one("#code-action-bar").display = False

        cv = self.query_one("#code-view", CodeView)
        cv.is_diff = False
        cv.filepath = str(path)
        cv.content = content

    def load_patch_set(self, patch_set: PatchSet) -> None:
        self.patch_set = patch_set
        self.multi_patch_set = None
        self.current_patch_idx = 0
        self.current_hunk_idx = 0
        self.query_one("#code-action-bar").display = True
        self.query_one("#diff-controls").remove_class("hidden")
        self.query_one("#multi-agent-controls").add_class("hidden")
        self._refresh_diff_view()

    def load_multi_patch_set(self, mps: MultiAgentPatchSet) -> None:
        if not mps.patch_sets:
            return
        self.multi_patch_set = mps
        self.agent_idx = 0
        self.patch_set = mps.patch_sets[self.agent_idx]
        self.current_patch_idx = 0
        self.current_hunk_idx = 0
        self.query_one("#code-action-bar").display = True
        self.query_one("#diff-controls").remove_class("hidden")
        self.query_one("#multi-agent-controls").remove_class("hidden")
        self._update_agent_label()
        self._refresh_diff_view()

    def _refresh_diff_view(self) -> None:
        if not self.patch_set or not self.patch_set.patches:
            return
        patch = self.patch_set.patches[self.current_patch_idx]
        cv = self.query_one("#code-view", CodeView)
        cv.is_diff = True
        cv.patch = patch
        cv.filepath = patch.file_path
        self._update_buttons()

    def _update_buttons(self) -> None:
        if not self.patch_set:
            return
        patch = self.patch_set.patches[self.current_patch_idx]
        hunk = patch.hunks[self.current_hunk_idx]
        app_btn = self.query_one("#btn-approve", Button)
        rej_btn = self.query_one("#btn-reject", Button)
        app_btn.variant = "success" if hunk.status != "approved" else "default"
        rej_btn.variant = "error" if hunk.status != "rejected" else "default"

    def _update_agent_label(self) -> None:
        if not self.multi_patch_set:
            return
        label = self.query_one("#multi-agent-label", Label)
        ps = self.patch_set
        agent_name = f"{ps.agent_id} ({ps.model_name})" if ps else "Unknown"
        label.update(
            f"Viewing: {agent_name} [{self.agent_idx + 1}/{len(self.multi_patch_set.patch_sets)}]"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self.multi_patch_set:
            if event.button.id == "btn-next-agent":
                self.agent_idx = (self.agent_idx + 1) % len(self.multi_patch_set.patch_sets)
                self.patch_set = self.multi_patch_set.patch_sets[self.agent_idx]
                self.current_patch_idx = 0
                self.current_hunk_idx = 0
                self._update_agent_label()
                self._refresh_diff_view()
                return
            elif event.button.id == "btn-prev-agent":
                self.agent_idx = (self.agent_idx - 1) % len(self.multi_patch_set.patch_sets)
                self.patch_set = self.multi_patch_set.patch_sets[self.agent_idx]
                self.current_patch_idx = 0
                self.current_hunk_idx = 0
                self._update_agent_label()
                self._refresh_diff_view()
                return

        if not self.patch_set:
            return
        patch = self.patch_set.patches[self.current_patch_idx]
        hunk = patch.hunks[self.current_hunk_idx]

        if event.button.id == "btn-approve":
            hunk.status = "approved"
            self.action_next_hunk()
        elif event.button.id == "btn-reject":
            hunk.status = "rejected"
            self.action_next_hunk()
        elif event.button.id == "btn-prev-hunk":
            self.action_prev_hunk()
        elif event.button.id == "btn-next-hunk":
            self.action_next_hunk()
        elif event.button.id == "btn-apply-all":
            self._apply_patches()

        self._refresh_diff_view()

    def action_next_hunk(self) -> None:
        if not self.patch_set:
            return
        patch = self.patch_set.patches[self.current_patch_idx]
        if self.current_hunk_idx < len(patch.hunks) - 1:
            self.current_hunk_idx += 1
        elif self.current_patch_idx < len(self.patch_set.patches) - 1:
            self.current_patch_idx += 1
            self.current_hunk_idx = 0

    def action_prev_hunk(self) -> None:
        if not self.patch_set:
            return
        if self.current_hunk_idx > 0:
            self.current_hunk_idx -= 1
        elif self.current_patch_idx > 0:
            self.current_patch_idx -= 1
            self.current_hunk_idx = len(self.patch_set.patches[self.current_patch_idx].hunks) - 1

    def _apply_patches(self) -> None:
        from src.core.elo_tracker import EloTracker
        from src.core.events import PatchApplied
        from src.tui.overlays.receipt import BuildReceipt

        engine = PatchEngine()
        winner_name = "Unknown"
        loser_names = []

        if self.multi_patch_set:
            modified = engine.apply_multi_approved(self.multi_patch_set)

            # ELO Recording
            try:
                tracker = EloTracker()
                winner_id = self.patch_set.model_id if hasattr(self.patch_set, "model_id") else self.patch_set.model_name  # noqa: E501
                winner_name = self.patch_set.model_name

                loser_ids = []
                for ps in self.multi_patch_set.patch_sets:
                    ps_id = ps.model_id if hasattr(ps, "model_id") else ps.model_name
                    if ps_id != winner_id:
                        loser_ids.append(ps_id)
                        loser_names.append(ps.model_name)

                tracker.record_match(
                    winner_id=winner_id,
                    loser_ids=loser_ids,
                    complexity=len(modified),
                    duration_sec=getattr(self.patch_set, "generation_time", 5.0),
                    costs={ps.model_id if hasattr(ps, "model_id") else ps.model_name: getattr(ps, "cost", 0.05) for ps in self.multi_patch_set.patch_sets}  # noqa: E501
                )
            except Exception as e:
                logger.debug(f"ELO recording failed: {e}")

        else:
            modified = engine.apply_approved(self.patch_set)
            if self.patch_set:
                winner_name = self.patch_set.model_name

        for fp in modified:
            self.post_message(PatchApplied(filepath=fp))

        self.query_one("#code-action-bar").display = False
        self.query_one("#diff-controls").add_class("hidden")
        self.query_one("#multi-agent-controls").add_class("hidden")
        self.query_one("#code-view").is_diff = False
        self.query_one("#code-view").update(f"Patches applied to {len(modified)} files.")

        # Display the Viral Build Receipt Modal
        try:
            duration = self.patch_set.generation_time if self.patch_set else 0.0
            receipt_cost = self.patch_set.cost_usd if self.patch_set else 0.0

            self.app.push_screen(BuildReceipt(
                winner_name=winner_name,
                loser_names=loser_names,
                duration_sec=duration,
                cost=receipt_cost,
                files_changed=len(modified)
            ))

            # Attempt to refresh global leaderboard if it exists in the tree
            from src.tui.panels.leaderboard import LeaderboardPanel
            try:
                lb = self.app.query_one(LeaderboardPanel)
                lb.refresh_data()
            except Exception as e:
                logger.debug(f"Leaderboard refresh failed: {e}")
        except Exception as e:
            logger.debug(f"Receipt rendering failed: {e}")

    def action_enter_selection(self) -> None:
        """Enter selection mode in the code view."""
        cv = self.query_one("#code-view", CodeView)
        if not cv.is_diff:
            cv.enter_selection_mode()

    def action_extend_down(self) -> None:
        """Extend selection one line down."""
        cv = self.query_one("#code-view", CodeView)
        if cv.selection_manager.is_active:
            cv.extend_selection_down()

    def action_extend_up(self) -> None:
        """Extend selection one line up."""
        cv = self.query_one("#code-view", CodeView)
        if cv.selection_manager.is_active:
            cv.extend_selection_up()

    def action_confirm_selection(self) -> None:
        """Confirm the current selection."""
        cv = self.query_one("#code-view", CodeView)
        if cv.selection_manager.is_active:
            cv.confirm_selection()

    def action_cancel_selection(self) -> None:
        """Cancel selection mode."""
        cv = self.query_one("#code-view", CodeView)
        if cv.selection_manager.is_active:
            cv.exit_selection_mode()

    def on_code_line_clicked(self, event: CodeLineClicked) -> None:
        """Forward line click events to the CodeView's selection handler."""
        cv = self.query_one("#code-view", CodeView)
        cv.handle_line_clicked(event.line_number, event.shift_held)

    def action_edit_hunk(self) -> None:
        cv = self.query_one("#code-view", CodeView)
        if not cv.is_diff or not self.patch_set:
            return

        from src.tui.widgets.hunk_editor import HunkEditor

        # Don't prompt if already editing
        if cv.query(HunkEditor):
            return

        patch = self.patch_set.patches[self.current_patch_idx]
        hunk = patch.hunks[self.current_hunk_idx]

        editor = HunkEditor(
            file_path=patch.file_path,
            hunk_index=self.current_hunk_idx,
            modified_lines=hunk.modified_lines,
        )

        # Hide the diff text while editing
        diff_view = cv.query_one("#code-diff-view", Static)
        diff_view.display = False

        cv.mount(editor)
        editor.focus()

    from textual import on

    from src.tui.widgets.hunk_editor import HunkEditor

    @on(HunkEditor.EditApplied)
    def on_hunk_edit_applied(self, event: HunkEditor.EditApplied) -> None:
        """Apply the edited text to the hunk."""
        event.stop()
        if not self.patch_set:
            return

        patch = self.patch_set.patches[self.current_patch_idx]
        hunk = patch.hunks[event.hunk_index]
        hunk.user_edited = True
        hunk.user_text = event.edited_text
        hunk.status = "approved"  # Automatically approve user edits

        # Emit system event as requested by the plan
        from src.core.events import HunkEditCompleted

        self.post_message(
            HunkEditCompleted(
                file_path=patch.file_path,
                hunk_index=event.hunk_index,
                edited_text=event.edited_text,
            )
        )

        self._cleanup_editor(event.control)

    @on(HunkEditor.EditCancelled)
    def on_hunk_edit_cancelled(self, event: HunkEditor.EditCancelled) -> None:
        """Discard the edit and restore the diff view."""
        event.stop()

        from src.core.events import HunkEditCompleted

        self.post_message(
            HunkEditCompleted(
                file_path=event.file_path,
                hunk_index=event.hunk_index,
                edited_text="",
                was_cancelled=True,
            )
        )

        self._cleanup_editor(event.control)

    def _cleanup_editor(self, editor_widget) -> None:
        """Remove the editor and restore the diff view."""
        editor_widget.remove()
        cv = self.query_one("#code-view", CodeView)
        cv.query_one("#code-diff-view", Static).display = True
        self._refresh_diff_view()
        self.focus()

    def action_toggle_annotations(self) -> None:
        """Toggle the visibility of inline annotations."""
        cv = self.query_one("#code-view", CodeView)
        cv.annotation_manager.toggle_visibility()
        cv.refresh_annotations()

        from src.tui.widgets.annotations import AnnotationPanel

        if not cv.annotation_manager.is_visible:
            for p in cv.query(AnnotationPanel):
                p.remove()

    from src.core.events import AnnotationsReady
    from src.tui.widgets.annotations import AnnotationGutter, AnnotationPanel

    @on(AnnotationGutter.Clicked)
    def on_annotation_gutter_clicked(self, event: "AnnotationGutter.Clicked") -> None:
        """Mount the AnnotationPanel below the clicked code line."""
        event.stop()
        cv = self.query_one("#code-view", CodeView)
        scroll = cv.query_one("#code-lines-scroll", VerticalScroll)

        from src.tui.widgets.annotations import AnnotationPanel

        existing = scroll.query(AnnotationPanel)
        for p in existing:
            if p.annotation.line_number == event.annotation.line_number:
                p.remove()
                return

        line_widget = event.control.parent
        panel = AnnotationPanel(annotation=event.annotation, file_path=str(cv.filepath))
        scroll.mount(panel, after=line_widget)

    @on(AnnotationPanel.Closed)
    def on_annotation_panel_closed(self, event: "AnnotationPanel.Closed") -> None:
        """Close the AnnotationPanel."""
        event.stop()
        event.control.remove()

    @on(AnnotationsReady)
    def on_annotations_ready(self, event: AnnotationsReady) -> None:
        """Load newly received annotations."""
        cv = self.query_one("#code-view", CodeView)
        if str(cv.filepath) == event.file_path:
            cv.annotation_manager.load_annotations(event.annotations)
            cv.refresh_annotations()
