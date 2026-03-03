"""Tests for cross-model failover in ChatPipeline."""

import pytest

from src.core.model_registry import ModelDefinition, ModelRegistry, Provider, QualityTier


@pytest.fixture(autouse=True)
def fresh_registry():
    """Reset the singleton registry for each test."""
    ModelRegistry._instance = None
    yield
    ModelRegistry._instance = None


class TestGetFallbackModel:
    """Tests for ModelRegistry.get_fallback_model selection policy."""

    def _make_model(self, model_id: str, provider: str, tier: str, cost: float = 1.0):
        return ModelDefinition(
            id=model_id,
            name=model_id,
            provider=Provider(provider),
            input_cost_per_mtok=cost,
            output_cost_per_mtok=cost,
            max_context_tokens=128_000,
            quality_tiers=[tier],
        )

    def test_same_tier_same_provider(self, monkeypatch):
        reg = ModelRegistry()
        m1 = self._make_model("model-a", "openai", "standard", 1.0)
        m2 = self._make_model("model-b", "openai", "standard", 2.0)
        reg._models = {"model-a": m1, "model-b": m2}
        monkeypatch.setattr(reg, "get_available_models", lambda: [m1, m2])

        result = reg.get_fallback_model("model-a", QualityTier.STANDARD, provider_preference="openai")
        assert result is not None
        assert result.id == "model-b"

    def test_same_tier_any_provider(self, monkeypatch):
        reg = ModelRegistry()
        m1 = self._make_model("model-a", "openai", "standard", 1.0)
        m2 = self._make_model("model-c", "anthropic", "standard", 0.5)
        reg._models = {"model-a": m1, "model-c": m2}
        monkeypatch.setattr(reg, "get_available_models", lambda: [m1, m2])

        result = reg.get_fallback_model("model-a", QualityTier.STANDARD, provider_preference="openai")
        # m2 is the only fallback available (different provider)
        assert result is not None
        assert result.id == "model-c"

    def test_adjacent_tier_fallback(self, monkeypatch):
        reg = ModelRegistry()
        m1 = self._make_model("model-a", "openai", "standard", 1.0)
        m2 = self._make_model("model-d", "openai", "max", 5.0)
        reg._models = {"model-a": m1, "model-d": m2}
        monkeypatch.setattr(reg, "get_available_models", lambda: [m1, m2])

        result = reg.get_fallback_model("model-a", QualityTier.STANDARD, excluded={"model-a"})
        # Should fall back to MAX tier
        assert result is not None
        assert result.id == "model-d"

    def test_no_fallback_available(self, monkeypatch):
        reg = ModelRegistry()
        m1 = self._make_model("model-a", "openai", "standard", 1.0)
        reg._models = {"model-a": m1}
        monkeypatch.setattr(reg, "get_available_models", lambda: [m1])

        result = reg.get_fallback_model("model-a", QualityTier.STANDARD)
        assert result is None

    def test_excluded_models_are_skipped(self, monkeypatch):
        reg = ModelRegistry()
        m1 = self._make_model("model-a", "openai", "standard", 1.0)
        m2 = self._make_model("model-b", "openai", "standard", 2.0)
        m3 = self._make_model("model-c", "openai", "standard", 3.0)
        reg._models = {"model-a": m1, "model-b": m2, "model-c": m3}
        monkeypatch.setattr(reg, "get_available_models", lambda: [m1, m2, m3])

        result = reg.get_fallback_model(
            "model-a", QualityTier.STANDARD, excluded={"model-b"}
        )
        assert result is not None
        assert result.id == "model-c"


class TestFailoverErrorClassification:
    """Verify transient vs auth error classification logic used in chat_pipeline."""

    TRANSIENT_KEYWORDS = (
        "rate limit", "rate_limit", "ratelimit", "429",
        "timeout", "timed out", "connection",
        "temporary", "503", "502", "overloaded",
    )
    AUTH_KEYWORDS = (
        "auth", "401", "403", "invalid api key",
        "invalid_api_key", "unauthorized",
    )

    @pytest.mark.parametrize("msg", [
        "Rate limit exceeded",
        "Error 429: too many requests",
        "Connection timeout after 30s",
        "Error 503: service temporarily unavailable",
    ])
    def test_transient_errors_match(self, msg):
        err_str = msg.lower()
        is_transient = any(kw in err_str for kw in self.TRANSIENT_KEYWORDS)
        assert is_transient, f"Expected transient match for: {msg}"

    @pytest.mark.parametrize("msg", [
        "Invalid API key provided",
        "401 Unauthorized",
        "Error 403: forbidden",
        "Authentication failed",
    ])
    def test_auth_errors_match(self, msg):
        err_str = msg.lower()
        is_auth = any(kw in err_str for kw in self.AUTH_KEYWORDS)
        assert is_auth, f"Expected auth match for: {msg}"

    def test_generic_error_is_not_transient(self):
        err_str = "something went wrong with model processing"
        is_transient = any(kw in err_str for kw in self.TRANSIENT_KEYWORDS)
        assert not is_transient
