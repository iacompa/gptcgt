import logging
import re
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from src.core.model_registry import ModelRegistry

logger = logging.getLogger(__name__)
router = APIRouter(tags=["models"])

class ModelResponse(BaseModel):
    id: str
    name: str
    provider: str
    tier: str

def natural_sort_key(text: str) -> list:
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

def model_sort_key(model_id: str, label: str) -> tuple:
    if not model_id:
        return ("000_default", [])

    if model_id.startswith("openrouter/"):
        parts = model_id.replace("openrouter/", "").split("/")
        provider = parts[0].lower() if len(parts) >= 2 else "openrouter"
    elif "/" in model_id:
        provider = model_id.split("/")[0].lower()
    else:
        provider = "zzz_other"

    return (provider, natural_sort_key(label))

@router.get("", response_model=List[ModelResponse])
async def get_available_models():
    """Return a sorted list of all available models based on active API keys."""
    registry = ModelRegistry()
    if not registry.get_all():
        registry.load()

    from src.auth.keychain import KeyChainManager
    if KeyChainManager.get_key("OPENROUTER_API_KEY"):
        has_or = any(m.id.startswith("openrouter/") for m in registry.get_all())
        if not has_or:
            try:
                data = await registry.fetch_openrouter_models()
                if data:
                    from src.core.model_registry import QualityTier
                    for m in data:
                        name = m.get("name", m.get("id"))
                        m_id = m.get("id")
                        registry.register_custom_openrouter_model(m_id, name, QualityTier.STANDARD, openrouter_data=data)
            except Exception as e:
                logger.error(f"Failed to fetch openrouter models: {e}")

    models = registry.get_available_models()

    result = []
    for m in models:
        parts = m.id.split("/")
        prov_display = m.provider.value.capitalize()
        if m.id.startswith("openrouter/") and len(parts) >= 3:
            prov_display = f"OpenRouter ({parts[1].capitalize()})"

        result.append({
            "id": m.id,
            "name": m.name,
            "provider": prov_display,
            "tier": m.quality_tiers[0] if m.quality_tiers else "standard"
        })

    result.sort(key=lambda x: model_sort_key(x["id"], x["name"]))
    return result
