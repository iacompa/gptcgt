"""Tests for Cost Breakdown Tracker."""

import pytest
from src.billing.cost_breakdown import CostBreakdownTracker, ModelUsage

def test_task_cost_sums_models():
    tracker = CostBreakdownTracker()
    tracker.start_task("t1", "Test Task", "standard", "standard", 5)
    
    m1 = ModelUsage("m1", "M1", "prov", "role", input_tokens=1000, output_tokens=500, total_cost=0.01)
    m2 = ModelUsage("m2", "M2", "prov", "role", input_tokens=2000, output_tokens=1000, total_cost=0.05)
    
    tracker.record_model_usage(m1)
    tracker.record_model_usage(m2)
    
    task = tracker.finish_task()
    assert task.total_cost == 0.06
    assert task.total_input_tokens == 3000
    assert task.most_expensive_model.model_id == "m2"

def test_refusal_not_charged():
    tracker = CostBreakdownTracker()
    tracker.start_task("t2", "Test Refusal", "standard", "standard", 5)
    
    m1 = ModelUsage("m1", "M1", "prov", "role", total_cost=0.05, was_refusal=True)
    m2 = ModelUsage("m2", "M2", "prov", "role", total_cost=0.02, was_refusal=False)
    
    tracker.record_model_usage(m1)
    tracker.record_model_usage(m2)
    
    task = tracker.finish_task()
    # The sum shouldn't include the refusal
    assert task.total_cost == 0.02
    
def test_daily_spend_accumulates():
    tracker = CostBreakdownTracker()
    tracker.start_task("t1", "T1", "scout", "light", 1)
    tracker.record_model_usage(ModelUsage("m1", "M1", "prov", "role", total_cost=0.01))
    tracker.finish_task()
    
    tracker.start_task("t2", "T2", "standard", "standard", 5)
    tracker.record_model_usage(ModelUsage("m2", "M2", "prov", "role", total_cost=0.05))
    tracker.finish_task()
    
    today = tracker.get_today_spend()
    assert today.task_count == 2
    assert today.total_cost == 0.06
    assert today.total_credits == 6

def test_model_ranking_sorted_by_cost():
    tracker = CostBreakdownTracker()
    tracker.start_task("t1", "T1", "standard", "standard", 5)
    tracker.record_model_usage(ModelUsage("m_cheap", "MC", "prov", "role", total_cost=0.01))
    tracker.record_model_usage(ModelUsage("m_exp", "ME", "prov", "role", total_cost=0.10))
    tracker.finish_task()
    
    ranking = tracker.get_model_ranking()
    assert len(ranking) == 2
    assert ranking[0]["model"] == "m_exp"
    assert ranking[1]["model"] == "m_cheap"
