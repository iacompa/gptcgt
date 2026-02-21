"""Tests for Overage Manager."""

import pytest
from src.billing.overage import OverageManager

def test_proceed_when_credits_available():
    manager = OverageManager()
    manager.state.plan_credits = 1000
    manager.state.remaining_credits = 1000
    
    res = manager.check_can_proceed(5)
    assert res["can_proceed"] is True
    assert res["action"] == "proceed"

def test_warn_when_low_credits():
    manager = OverageManager()
    manager.state.plan_credits = 1000
    manager.state.remaining_credits = 4
    manager.state.overage_enabled = True
    
    res = manager.check_can_proceed(5)
    assert res["can_proceed"] is True
    assert res["action"] == "warn"

def test_block_when_no_credits_no_overage():
    manager = OverageManager()
    manager.state.plan_credits = 1000
    manager.state.remaining_credits = 0
    manager.state.overage_enabled = False
    manager.state.auto_downgrade = False
    
    res = manager.check_can_proceed(5)
    assert res["can_proceed"] is False
    assert res["action"] == "block"

def test_allow_overage_when_enabled():
    manager = OverageManager()
    manager.state.plan_credits = 1000
    manager.state.remaining_credits = 0
    manager.state.overage_enabled = True
    
    res = manager.check_can_proceed(5)
    assert res["can_proceed"] is True
    assert res["action"] == "proceed"

def test_auto_downgrade_to_light_scout():
    manager = OverageManager()
    manager.state.plan_credits = 1000
    manager.state.remaining_credits = 0
    manager.state.overage_enabled = False
    manager.state.auto_downgrade = True
    
    res = manager.check_can_proceed(5)
    assert res["can_proceed"] is True
    assert res["action"] == "downgrade"
