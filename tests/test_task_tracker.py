"""Tests for Task Tracker."""

import pytest
from src.core.task_tracker import TaskTracker, TaskStatus, SUBTASK_TEMPLATES

def test_standard_template_has_7_subtasks():
    assert len(SUBTASK_TEMPLATES["standard"]) == 7

def test_progress_calculation():
    tracker = TaskTracker()
    task = tracker.create_task("Test", "scout", "light") # 2 subtasks in scout
    
    assert task.progress_pct == 0.0
    
    tracker.start_subtask(task.id, task.subtasks[0].id)
    assert task.progress_pct == 0.0
    
    tracker.complete_subtask(task.id, task.subtasks[0].id)
    assert task.progress_pct == 50.0
    
    tracker.complete_subtask(task.id, task.subtasks[1].id)
    assert task.progress_pct == 100.0

def test_active_subtask_returns_in_progress():
    tracker = TaskTracker()
    task = tracker.create_task("Test", "scout", "light")
    
    assert task.current_subtask is None
    tracker.start_subtask(task.id, task.subtasks[0].id)
    
    active = task.current_subtask
    assert active is not None
    assert active.id == task.subtasks[0].id

def test_task_history_most_recent_first():
    tracker = TaskTracker()
    t1 = tracker.create_task("T1", "scout")
    tracker.complete_task(t1.id)
    t2 = tracker.create_task("T2", "standard")
    
    history = tracker.get_task_history()
    assert len(history) == 2
    assert history[0].id == t2.id
    assert history[1].id == t1.id
