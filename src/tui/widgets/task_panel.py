from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static
from textual.reactive import reactive

from src.core.task_tracker import TaskTracker, Task, TaskStatus

class TaskPanel(VerticalScroll):
    """
    Visual task tracker in the LEFT panel, above the file tree.
    """
    
    DEFAULT_CSS = """
    TaskPanel {
        border-bottom: solid #30363D;
        height: auto;
        max-height: 50%;
        padding: 1;
        background: #161B22;
        display: none;
    }
    TaskPanel.-active {
        display: block;
    }
    .task-title {
        text-style: bold;
        color: #E6EDF3;
        margin-bottom: 1;
    }
    .subtask {
        padding-left: 2;
        color: #8B949E;
    }
    .subtask.-in-progress {
        color: #58A6FF;
    }
    .subtask.-completed {
        color: #3FB950;
    }
    .subtask.-failed {
        color: #F85149;
    }
    """

    tracker: reactive[TaskTracker | None] = reactive(None)

    def watch_tracker(self, old: TaskTracker | None, new: TaskTracker | None) -> None:
        self._update_display()

    def _update_display(self) -> None:
        if not self.tracker:
            self.display = False
            return
            
        active = self.tracker.get_active_task()
        if not active:
            # Maybe show recent completed if needed, else hide
            self.display = False
            return
            
        self.display = True
        self.remove_children()
        
        # Re-render
        with self.app.batch_update():
            self.mount(Static(f"▼ {active.title} ({int(active.progress_pct)}%)", classes="task-title"))
            
            for st in active.subtasks:
                icon = "⬚"
                cls = "subtask"
                if st.status == TaskStatus.IN_PROGRESS:
                    icon = "🔄"
                    cls += " -in-progress"
                elif st.status == TaskStatus.COMPLETED:
                    icon = "✅"
                    cls += " -completed"
                elif st.status == TaskStatus.FAILED:
                    icon = "❌"
                    cls += " -failed"
                elif st.status == TaskStatus.WAITING:
                    icon = "⏳"
                
                # Show elapsed time if completed or in progress
                time_str = ""
                if st.started_at:
                    end = st.completed_at or __import__('datetime').datetime.now()
                    elapsed = (end - st.started_at).total_seconds()
                    time_str = f"  {elapsed:.1f}s"
                    
                self.mount(Static(f"{icon} {st.title}{time_str}", classes=cls))
