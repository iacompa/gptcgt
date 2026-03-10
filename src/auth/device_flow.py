import asyncio
from typing import Any, Dict, Optional

import httpx


class DeviceFlowClient:
    """Client for handling the OAuth device authorization flow."""

    def __init__(self, base_url: str = "https://gptcgt-api.fly.dev"):
        self.base_url = base_url.rstrip("/")

    async def start_flow(self, client_id: str) -> Dict[str, Any]:
        """
        Starts the device flow by requesting a device code.
        Returns: {device_code, user_code, verification_uri}
        """
        if not client_id:
            raise ValueError("client_id cannot be empty")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f"{self.base_url}/auth/device", params={"client_id": client_id})
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError:
                raise

    async def poll_for_token(
        self, device_code: str, interval: int = 5, max_attempts: int = 60
    ) -> Optional[Dict[str, Any]]:
        """
        Polls the server until the user authorizes the device code.
        Times out after max_attempts polls (default: 60 * 5s = 5 minutes).
        Returns None on timeout.
        """
        async with httpx.AsyncClient() as client:
            for attempt in range(max_attempts):
                try:
                    response = await client.post(f"{self.base_url}/auth/token", json={"device_code": device_code})

                    if response.status_code == 200:
                        data = response.json()
                        return {
                            "access_token": data.get("access_token"),
                            "refresh_token": data.get("refresh_token"),
                        }
                    elif response.status_code == 400:
                        data = response.json()
                        error = data.get("error")
                        if error is None and isinstance(data.get("detail"), dict):
                            error = data["detail"].get("error")
                        if error == "authorization_pending":
                            await asyncio.sleep(interval)
                            continue
                        elif error == "slow_down":
                            await asyncio.sleep(interval + 5)
                            continue
                        elif error == "expired_token":
                            raise Exception("The device code has expired. Please try again.")
                        else:
                            raise Exception(f"Authorization error: {error}")

                except httpx.HTTPError:
                    raise

                await asyncio.sleep(interval)

            # Timed out
            return None
