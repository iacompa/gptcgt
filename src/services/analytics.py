"""PostHog integration for usage telemetry."""

import logging

import httpx

from src.services.registry import services

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self):
        self.config = services.posthog

    async def track_async(self, distinct_id: str, event: str, properties: dict = None):
        if not self.config.is_configured:
            return False

        payload = {
            "api_key": self.config.api_key,
            "event": event,
            "properties": {"distinct_id": distinct_id, **(properties or {})},
        }
        try:
            async with httpx.AsyncClient(base_url=self.config.host) as client:
                resp = await client.post("/capture/", json=payload, timeout=3.0)
                resp.raise_for_status()
            return True
        except Exception as e:
            logger.debug(f"Failed to track event {event}: {e}")
            return False


_analytics = AnalyticsService()


def track(distinct_id: str, event: str, properties: dict = None):
    """Fire and forget track function for synchronous callers (like TUI)."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_analytics.track_async(distinct_id, event, properties))
    except RuntimeError:
        pass  # Not in an active async environment or loop


async def track_async(distinct_id: str, event: str, properties: dict = None):
    return await _analytics.track_async(distinct_id, event, properties)
