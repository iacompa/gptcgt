"""Tests for Quality Tiers."""

import pytest
from src.core.quality_tiers import QualityTierManager, QualityTier, TIER_CONFIGS

def test_default_tier_is_standard():
    manager = QualityTierManager()
    assert manager.active_tier == QualityTier.STANDARD
    assert manager.config == TIER_CONFIGS[QualityTier.STANDARD]

def test_cycle_tier_order():
    manager = QualityTierManager()
    # Assuming STANDARD is default
    assert manager.active_tier == QualityTier.STANDARD
    
    manager.cycle_tier()
    assert manager.active_tier == QualityTier.MAX
    
    manager.cycle_tier()
    assert manager.active_tier == QualityTier.LIGHT
    
    manager.cycle_tier()
    assert manager.active_tier == QualityTier.STANDARD

def test_light_tier_prefers_cheap_models():
    manager = QualityTierManager()
    manager.set_tier(QualityTier.LIGHT)
    prefs = manager.get_preferred_models("coding")
    # Quick check for non-premium models
    assert any("mini" in m.lower() or "flash" in m.lower() or "deepseek" in m.lower() for m in prefs)

def test_max_tier_prefers_premium_models():
    manager = QualityTierManager()
    manager.set_tier(QualityTier.MAX)
    prefs = manager.get_preferred_models("coding")
    # Quick check for premium models
    assert any("opus" in m.lower() or "gpt-4" in m.lower() for m in prefs)
