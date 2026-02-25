from src.core.model_registry import ModelRegistry, Provider, QualityTier


def test_load_bundled_models():
    registry = ModelRegistry()
    registry.load()  # Will load default models.json

    assert registry._loaded
    # Check that we parsed the models correctly
    claude = registry.get("anthropic/claude-sonnet-4-20250514")
    assert claude is not None
    assert claude.provider == Provider.ANTHROPIC
    assert claude.input_cost_per_mtok == 3.0

    gpt4 = registry.get("openai/gpt-4o")
    assert gpt4 is not None
    assert gpt4.provider == Provider.OPENAI


def test_get_models_for_tier():
    registry = ModelRegistry()
    # If not loaded by a previous test due to order or fresh instance, load it
    if not registry._loaded:
        registry.load()

    light_models = registry.get_models_for_tier(QualityTier.LIGHT)
    assert len(light_models) > 0
    # Must be sorted by cost
    assert light_models[0].input_cost_per_mtok <= light_models[-1].input_cost_per_mtok


def test_calculate_cost():
    registry = ModelRegistry()
    if not registry._loaded:
        registry.load()

    cost = registry.calculate_cost("anthropic/claude-sonnet-4-20250514", 1_000_000, 1_000_000)
    # 3.0 input + 15.0 output
    assert cost == 18.0


def test_get_cheapest_model():
    registry = ModelRegistry()
    if not registry._loaded:
        registry.load()

    cheapest = registry.get_cheapest_model()
    # It should be haiku, gpt4omini, gemini-flash, or deepseek
    assert cheapest.input_cost_per_mtok <= 0.80
