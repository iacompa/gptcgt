"""Tests for the execution state progress-tracking system."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.execution_state import (
    VALID_TRANSITIONS,
    ChecklistItem,
    ContextSlicer,
    ExecutionState,
    ItemStatus,
    ScopeChangeEngine,
    is_excluded_path,
)

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def state(tmp_path: Path) -> ExecutionState:
    """Fresh execution state rooted in a temp dir."""
    (tmp_path / ".gptcgt").mkdir()
    return ExecutionState(tmp_path)


@pytest.fixture
def populated_state(state: ExecutionState) -> ExecutionState:
    """State with a small dependency graph: A → B → C."""
    a = state.add_item("Setup project", category="Foundation")
    b = state.add_item(
        "Implement auth",
        category="Core",
        dependencies=[a.id],
        acceptance_criteria=["Login works", "JWT validated"],
    )
    _c = state.add_item(
        "Write tests",
        category="Testing",
        dependencies=[b.id],
        acceptance_criteria=["90% coverage"],
    )
    return state


# ── ChecklistItem ───────────────────────────────────────────────────────


class TestChecklistItem:
    def test_defaults(self):
        item = ChecklistItem(id="abc123", title="Do thing")
        assert item.status == "pending"
        assert item.model_tier == "standard"
        assert item.route == "single"
        assert item.risk_level == "low"
        assert item.created_at != ""
        assert item.updated_at == item.created_at

    def test_custom_fields(self):
        item = ChecklistItem(
            id="xyz",
            title="Hard task",
            category="infra",
            risk_level="critical",
            token_budget_in=8000,
        )
        assert item.category == "infra"
        assert item.risk_level == "critical"
        assert item.token_budget_in == 8000


# ── Status Transitions ──────────────────────────────────────────────────


class TestStatusTransitions:
    def test_valid_transitions_defined_for_all(self):
        for status in ItemStatus:
            assert status in VALID_TRANSITIONS

    def test_terminal_states_have_no_exits(self):
        assert VALID_TRANSITIONS[ItemStatus.COMPLETED] == set()
        assert VALID_TRANSITIONS[ItemStatus.CANCELED] == set()

    def test_pending_to_ready(self, state):
        item = state.add_item("Task A")
        assert state.update_status(item.id, "ready") is True
        assert state.items[item.id].status == "ready"

    def test_invalid_pending_to_completed(self, state):
        item = state.add_item("Task B")
        assert state.update_status(item.id, "completed") is False
        assert state.items[item.id].status == "pending"

    def test_full_lifecycle(self, state):
        item = state.add_item("Task C")
        assert state.update_status(item.id, "ready")
        assert state.update_status(item.id, "in_progress")
        assert state.update_status(item.id, "review")
        assert state.update_status(item.id, "completed")
        assert state.items[item.id].status == "completed"
        # Terminal — no more transitions
        assert state.update_status(item.id, "in_progress") is False

    def test_failure_recovery(self, state):
        item = state.add_item("Task D")
        state.update_status(item.id, "ready")
        state.update_status(item.id, "in_progress")
        state.update_status(item.id, "failed")
        # Should be able to retry
        assert state.update_status(item.id, "ready")
        assert state.items[item.id].status == "ready"

    def test_nonexistent_item(self, state):
        assert state.update_status("bogus_id", "ready") is False


# ── Serialization ────────────────────────────────────────────────────────


class TestSerialization:
    def test_json_roundtrip(self, populated_state):
        populated_state.save()
        path = populated_state._state_path
        assert path.exists()

        # Load into a fresh instance
        new_state = ExecutionState(populated_state.project_root)
        assert new_state.load() is True
        assert len(new_state.items) == len(populated_state.items)

        for item_id, item in populated_state.items.items():
            loaded = new_state.items[item_id]
            assert loaded.title == item.title
            assert loaded.category == item.category
            assert loaded.dependencies == item.dependencies

    def test_deterministic_output(self, populated_state):
        populated_state.save()
        content1 = populated_state._state_path.read_text()

        populated_state.save()
        content2 = populated_state._state_path.read_text()

        # Parse both and compare structure (timestamps will differ)
        d1 = json.loads(content1)
        d2 = json.loads(content2)
        # Items and plan ref should be identical
        assert d1["items"] == d2["items"]
        assert d1["project_plan_ref"] == d2["project_plan_ref"]

    def test_sorted_keys(self, populated_state):
        populated_state.save()
        content = populated_state._state_path.read_text()
        data = json.loads(content)
        # Top-level keys should be sorted
        assert list(data.keys()) == sorted(data.keys())

    def test_load_missing_file(self, state):
        assert state.load() is False

    def test_load_corrupted_file(self, state):
        state._state_path.write_text("not json at all!!!")
        assert state.load() is False


# ── Dependency Ordering ──────────────────────────────────────────────────


class TestDependencyOrdering:
    def test_topological_order(self, populated_state):
        order = populated_state.dependency_order()
        items_by_id = populated_state.items

        # Find the three items
        setup_id = next(i for i, it in items_by_id.items() if it.title == "Setup project")
        auth_id = next(i for i, it in items_by_id.items() if it.title == "Implement auth")
        tests_id = next(i for i, it in items_by_id.items() if it.title == "Write tests")

        # Setup must come before Auth, Auth before Tests
        assert order.index(setup_id) < order.index(auth_id)
        assert order.index(auth_id) < order.index(tests_id)

    def test_cycle_detection(self, state):
        a = state.add_item("A", category="cycle")
        b = state.add_item("B", category="cycle", dependencies=[a.id])
        # Create cycle: A depends on B
        a.dependencies = [b.id]

        assert state.has_cycle() is True
        with pytest.raises(ValueError, match="cycle"):
            state.dependency_order()

    def test_no_deps_order(self, state):
        state.add_item("Solo A")
        state.add_item("Solo B")
        order = state.dependency_order()
        assert len(order) == 2


# ── Ready Items ──────────────────────────────────────────────────────────


class TestReadyItems:
    def test_initial_ready(self, populated_state):
        ready = populated_state.get_ready_items()
        # Only "Setup project" has no dependencies
        assert len(ready) == 1
        assert ready[0].title == "Setup project"

    def test_after_completion(self, populated_state):
        setup_id = next(
            i for i, it in populated_state.items.items() if it.title == "Setup project"
        )
        # Complete Setup
        populated_state.items[setup_id].status = "completed"
        ready = populated_state.get_ready_items()
        # Now "Implement auth" should be ready
        assert any(r.title == "Implement auth" for r in ready)


# ── Migration ────────────────────────────────────────────────────────────


class TestMigration:
    def test_migrate_from_phase_md(self, state):
        phase_md = """# Project Phase Map
> Auto-generated by gptcgt

## Development Phases
### Phase 1: Foundation 🔄
- [x] Initial Setup
- [ ] Create config

### Phase 2: Core ⬚
- [ ] Implement auth
- [x] Add database
"""
        count = state.migrate_from_phase_md(phase_md)
        assert count == 4

        # Check statuses
        completed = state.get_items_by_status("completed")
        assert len(completed) == 2

        pending = state.get_items_by_status("pending")
        assert len(pending) == 2

    def test_migrate_from_plan_md(self, state):
        plan_md = """# Project Plan: Build API

## Phase 1: Foundation
- [x] Set up project structure
- [ ] Create core module scaffolding

## Phase 2: Core Implementation
- [/] Implement primary functionality
- [!] Add error handling (FAILED)
"""
        count = state.migrate_from_plan_md(plan_md)
        assert count == 4

        # Verify statuses
        items = list(state.items.values())
        statuses = {it.title: it.status for it in items}

        assert statuses["Set up project structure"] == "completed"
        assert statuses["Create core module scaffolding"] == "pending"
        assert statuses["Implement primary functionality"] == "in_progress"
        assert statuses["Add error handling"] == "failed"

    def test_migrate_preserves_categories(self, state):
        phase_md = """### Phase 1: Auth 🔄
- [ ] Login page
### Phase 2: API ⬚
- [ ] REST endpoints
"""
        state.migrate_from_phase_md(phase_md)
        categories = {it.category for it in state.items.values()}
        assert "Auth" in categories
        assert "API" in categories

    def test_migrate_idempotent(self, state):
        plan_md = "- [ ] Task A\n- [ ] Task B"
        state.migrate_from_plan_md(plan_md)
        count1 = len(state.items)
        state.migrate_from_plan_md(plan_md)
        count2 = len(state.items)
        assert count1 == count2  # No duplicates


# ── Artifact Exclusion ───────────────────────────────────────────────────


class TestArtifactExclusion:
    def test_node_modules_excluded(self):
        assert is_excluded_path("node_modules/react/index.js")

    def test_next_excluded(self):
        assert is_excluded_path(".next/cache/build.json")

    def test_dist_excluded(self):
        assert is_excluded_path("dist/bundle.js")

    def test_pycache_excluded(self):
        assert is_excluded_path("__pycache__/module.pyc")

    def test_git_excluded(self):
        assert is_excluded_path(".git/objects/abc123")

    def test_gptcgt_excluded(self):
        assert is_excluded_path(".gptcgt/phase.md")

    def test_normal_source_included(self):
        assert not is_excluded_path("src/core/main.py")

    def test_nested_source_included(self):
        assert not is_excluded_path("api/routes/users.py")

    def test_venv_excluded(self):
        assert is_excluded_path("venv/lib/python3.11/site.py")
        assert is_excluded_path(".venv/bin/activate")

    def test_egg_info_excluded(self):
        assert is_excluded_path("mypackage.egg-info/PKG-INFO")


# ── Context Slicing ──────────────────────────────────────────────────────


class TestContextSlicer:
    def test_orchestrator_view(self, populated_state):
        slicer = ContextSlicer(populated_state)
        ctx = slicer.for_orchestrator()
        assert "Execution Status" in ctx
        assert "0/3 done" in ctx

    def test_coder_view_has_criteria(self, populated_state):
        auth_id = next(
            i for i, it in populated_state.items.items() if it.title == "Implement auth"
        )
        slicer = ContextSlicer(populated_state)
        ctx = slicer.for_coder(auth_id)
        assert "Implement auth" in ctx
        assert "Login works" in ctx
        assert "JWT validated" in ctx

    def test_tester_view(self, populated_state):
        tests_id = next(
            i for i, it in populated_state.items.items() if it.title == "Write tests"
        )
        slicer = ContextSlicer(populated_state)
        ctx = slicer.for_tester(tests_id)
        assert "Write tests" in ctx
        assert "90% coverage" in ctx

    def test_arbiter_view(self, populated_state):
        ids = list(populated_state.items.keys())
        slicer = ContextSlicer(populated_state)
        ctx = slicer.for_arbiter(ids[:2])
        assert "Arbiter Review" in ctx

    def test_light_tier_budget(self, populated_state):
        slicer = ContextSlicer(populated_state)
        ctx = slicer.for_orchestrator(tier="light")
        assert len(ctx) <= 2000

    def test_max_tier_budget(self, populated_state):
        slicer = ContextSlicer(populated_state)
        ctx = slicer.for_orchestrator(tier="max")
        assert len(ctx) <= 12000

    def test_nonexistent_item(self, populated_state):
        slicer = ContextSlicer(populated_state)
        ctx = slicer.for_coder("bogus")
        assert "not found" in ctx

    def test_no_duplicate_data(self, populated_state):
        """Context views should not contain duplicate full-plan text."""
        slicer = ContextSlicer(populated_state)
        coder_ctx = slicer.for_coder(list(populated_state.items.keys())[1])
        # Coder should not see all items, only the assigned one + deps
        assert coder_ctx.count("Setup project") <= 1  # Dep only


# ── Scope Change Engine ──────────────────────────────────────────────────


class TestScopeChangeEngine:
    def test_submit_change_request(self, populated_state):
        engine = ScopeChangeEngine(populated_state)
        cr = engine.submit_change_request(
            title="Add OAuth",
            description="User wants Google OAuth",
            new_items=[
                {"title": "OAuth integration", "category": "Core"},
                {"title": "OAuth tests", "category": "Testing"},
            ],
        )
        assert cr.status == "proposed"
        assert len(cr.new_item_ids) == 2
        assert len(populated_state.items) == 5  # 3 original + 2 new

    def test_apply_change_request(self, populated_state):
        engine = ScopeChangeEngine(populated_state)
        # Complete the setup task so deps are met
        setup_id = next(
            i for i, it in populated_state.items.items() if it.title == "Setup project"
        )
        populated_state.items[setup_id].status = "completed"

        cr = engine.submit_change_request(
            title="Add logging",
            new_items=[
                {"title": "Logger module", "category": "Core", "dependencies": [setup_id]},
            ],
        )
        success = engine.apply_change_request(cr.id)
        assert success is True
        assert cr.status == "applied"
        # New item should be promoted to ready since its dep is completed
        logger_item = populated_state.items.get(cr.new_item_ids[0])
        assert logger_item is not None
        assert logger_item.status == "ready"

    def test_preserves_completed_work(self, populated_state):
        # Complete first two items
        for item in list(populated_state.items.values())[:2]:
            item.status = "completed"

        engine = ScopeChangeEngine(populated_state)
        engine.submit_change_request(
            title="Refactor",
            new_items=[{"title": "Big refactor", "category": "Refactoring"}],
        )

        # Completed items should be untouched
        completed = populated_state.get_items_by_status("completed")
        assert len(completed) == 2

    def test_reprioritize(self, populated_state):
        engine = ScopeChangeEngine(populated_state)
        order = engine.reprioritize()
        # Should return all items in dependency-safe order
        assert len(order) == len(populated_state.items)

    def test_nonexistent_cr(self, populated_state):
        engine = ScopeChangeEngine(populated_state)
        assert engine.apply_change_request("fake_id") is False

    def test_feature_insertion_no_corruption(self, populated_state):
        """Mid-run insertion must not corrupt progress of existing items."""
        # Mark first as in-progress
        setup_id = next(
            i for i, it in populated_state.items.items() if it.title == "Setup project"
        )
        populated_state.update_status(setup_id, "ready")
        populated_state.update_status(setup_id, "in_progress")

        engine = ScopeChangeEngine(populated_state)
        engine.submit_change_request(
            title="New feature",
            new_items=[{"title": "Dashboard", "category": "UI"}],
        )

        # Original items unchanged
        assert populated_state.items[setup_id].status == "in_progress"
        assert populated_state.items[setup_id].title == "Setup project"


# ── Derived Outputs ──────────────────────────────────────────────────────


class TestDerivedOutputs:
    def test_checklist_md_generated(self, populated_state):
        md = populated_state.to_checklist_md()
        assert "# Execution Checklist" in md
        assert "0/3 completed" in md
        assert "Setup project" in md

    def test_phase_md_backward_compatible(self, populated_state):
        md = populated_state.to_phase_md()
        assert "# Project Phase Map" in md
        assert "Auto-generated by gptcgt" in md
        assert "Development Phases" in md

    def test_phase_md_has_checkboxes(self, populated_state):
        md = populated_state.to_phase_md()
        assert "- [ ]" in md  # Pending items

    def test_write_derived_outputs(self, populated_state):
        populated_state.write_derived_outputs()
        gptcgt_dir = populated_state.project_root / ".gptcgt"
        assert (gptcgt_dir / "execution_checklist.md").exists()
        assert (gptcgt_dir / "phase.md").exists()

    def test_deterministic_derived_output(self, populated_state):
        """Same state produces identical derived outputs."""
        md1 = populated_state.to_checklist_md()
        md2 = populated_state.to_checklist_md()
        assert md1 == md2

    def test_completed_items_show_as_checked(self, state):
        item = state.add_item("Done task")
        item.status = "completed"
        md = state.to_phase_md()
        assert "- [x] Done task" in md

    def test_no_source_of_truth_divergence(self, populated_state):
        """JSON and derived outputs must reflect same count."""
        populated_state.save()
        populated_state.write_derived_outputs()

        json_data = json.loads(populated_state._state_path.read_text())
        checklist_md = (populated_state.project_root / ".gptcgt" / "execution_checklist.md").read_text()
        phase_md = (populated_state.project_root / ".gptcgt" / "phase.md").read_text()

        json_count = len(json_data["items"])
        # Count checkboxes in derived views
        checklist_boxes = checklist_md.count("- [")
        phase_boxes = phase_md.count("- [")

        assert json_count == checklist_boxes == phase_boxes
