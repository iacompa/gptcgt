from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "staging_smoke.py"
    spec = importlib.util.spec_from_file_location("staging_smoke", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_config_defaults(monkeypatch):
    smoke = _load_module()
    monkeypatch.setenv("SMOKE_API_URL", "https://staging.example.com/")
    monkeypatch.setenv("SMOKE_AUTH_TOKEN", "token-123")

    config = smoke.SmokeConfig.from_env()

    assert config.api_url == "https://staging.example.com"
    assert config.run_checkout_smoke is True
    assert config.checkout_plan == "pro"
    assert config.credit_purchase_amount == 100
    assert config.run_webhook_smoke is False
    assert config.run_hub_smoke is False


def test_webhook_requires_secret(monkeypatch):
    smoke = _load_module()
    monkeypatch.setenv("SMOKE_API_URL", "https://staging.example.com")
    monkeypatch.setenv("SMOKE_AUTH_TOKEN", "token-123")
    monkeypatch.setenv("SMOKE_RUN_WEBHOOK_SMOKE", "true")

    with pytest.raises(smoke.SmokeFailure, match="SMOKE_RUN_WEBHOOK_SMOKE requires SMOKE_STRIPE_WEBHOOK_SECRET"):
        smoke.SmokeConfig.from_env()


def test_hub_requires_repo_and_prompt(monkeypatch):
    smoke = _load_module()
    monkeypatch.setenv("SMOKE_API_URL", "https://staging.example.com")
    monkeypatch.setenv("SMOKE_AUTH_TOKEN", "token-123")
    monkeypatch.setenv("SMOKE_RUN_HUB_SMOKE", "true")
    monkeypatch.setenv("SMOKE_HUB_REPO_URL", "https://github.com/org/repo.git")

    with pytest.raises(smoke.SmokeFailure, match="SMOKE_RUN_HUB_SMOKE requires SMOKE_HUB_PROMPT"):
        smoke.SmokeConfig.from_env()


def test_build_noop_webhook_payload():
    smoke = _load_module()
    payload = smoke._build_noop_webhook_payload()
    decoded = smoke.json.loads(payload.decode("utf-8"))

    assert decoded["type"] == "smoke.noop"
    assert decoded["id"].startswith("evt_smoke_")
