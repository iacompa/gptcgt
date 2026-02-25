"""Betterstack integration for logs and heartbeats."""

import httpx

from src.services.registry import services


class InternalMonitoring:
    def __init__(self):
        self.config = services.betterstack

    async def log_exception(self, exc: Exception, context: dict = None):
        if not self.config.is_configured or not self.config.logs_token:
            return

        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    "https://in.logs.betterstack.com",
                    headers={"Authorization": f"Bearer {self.config.logs_token}"},
                    json={"message": str(exc), "context": context or {}},
                    timeout=5.0,
                )
        except Exception:
            pass

    async def heartbeat(self):
        if not self.config.is_configured or not self.config.heartbeat_url:
            return

        try:
            async with httpx.AsyncClient() as client:
                await client.get(self.config.heartbeat_url, timeout=3.0)
        except Exception:
            pass


monitor = InternalMonitoring()
