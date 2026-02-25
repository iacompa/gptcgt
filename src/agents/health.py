"""Agent health checker — verify all configured providers are reachable."""

import asyncio
import logging
from dataclasses import dataclass, field

from src.agents.factory import PROVIDER_KEY_MAP, AgentFactory
from src.auth.keychain import KeyChainManager
from src.core.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


@dataclass
class ProviderHealth:
    provider: str
    reachable: bool
    latency_ms: int | None = None
    error: str | None = None
    models: list[str] = field(default_factory=list)


async def check_all_providers() -> list[ProviderHealth]:
    """Check which providers are configured and reachable."""
    registry = ModelRegistry()
    results = []

    # Group available models by provider
    providers: dict[str, list] = {}
    for model_def in registry.get_available_models():
        prov = model_def.provider.value
        if prov not in providers:
            providers[prov] = []
        providers[prov].append(model_def)

    async def _check_single(provider_name: str, model_defs: list) -> ProviderHealth:
        key_name = PROVIDER_KEY_MAP.get(provider_name)
        if key_name:
            key = KeyChainManager.get_key(key_name)
        else:
            key = None

        if not key and provider_name != "custom":
            return ProviderHealth(
                provider=provider_name,
                reachable=False,
                error="No API key configured",
                models=[m.id for m in model_defs],
            )

        cheapest = min(model_defs, key=lambda m: m.input_cost_per_mtok)
        agent = AgentFactory.create_agent(cheapest, api_key=key)
        health = await agent.health_check()

        return ProviderHealth(
            provider=provider_name,
            reachable=health["reachable"],
            latency_ms=health.get("latency_ms"),
            error=health.get("error"),
            models=[m.id for m in model_defs],
        )

    tasks = [_check_single(name, models) for name, models in providers.items()]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    for item in results_list:
        if isinstance(item, Exception):
            logger.error(f"Health check task failed: {item}")
            continue
        results.append(item)

    return results
