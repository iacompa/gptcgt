from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from src.auth.device_flow import DeviceFlowClient
from src.auth.keychain import KeyChainManager

logger = logging.getLogger(__name__)


class AuthManager:
    """
    Manages authentication state, token refresh, and user profile.

    Token validation is intentionally lazy: __init__ trusts any stored token
    for instant startup, then validate_token_on_startup() should be awaited
    in the app's on_mount to verify the token is still valid server-side.
    This gives a fast startup while still catching expired/revoked tokens.
    """

    def __init__(self, base_url: str = "https://api.gptcgt.ai", client_id: str = "client_default"):
        self.base_url = base_url.rstrip("/")
        self._client_id = client_id
        self._device_client = DeviceFlowClient(base_url)
        self._profile: Dict[str, Any] | None = None
        self._is_authenticated = False

        # Quick local check — server validation happens via validate_token_on_startup()
        access, _ = KeyChainManager.get_auth_tokens()
        if access:
            self._is_authenticated = True

    async def validate_token_on_startup(self) -> None:
        """
        Async background validation: probes server to confirm token is live.

        - 200 OK  → profile cached, _is_authenticated = True
        - 401     → auto-refresh attempted, logout if refresh also fails
        - Network → keeps current state (offline graceful, won't log user out)

        Should be awaited in the app's on_mount so startup is not blocked.
        """
        if not self._is_authenticated:
            return
        try:
            profile = await self.fetch_user_profile()
            if profile:
                logger.debug("Token validated successfully on startup.")
            else:
                # fetch_user_profile already called self.logout() on unrecoverable 401
                logger.info("Token validation failed; user logged out.")
        except Exception as e:
            # Network failure — keep current state, don't log user out
            logger.debug(f"Token validation skipped (network unavailable): {e}")

    @property
    def is_authenticated(self) -> bool:
        return self._is_authenticated

    @property
    def user_plan(self) -> str:
        if not self._profile:
            return "free"
        return self._profile.get("plan", "free")

    @property
    def credits_remaining(self) -> int:
        if not self._profile:
            return 0
        return self._profile.get("credits_remaining", 0)

    @property
    def credits_monthly(self) -> int:
        """Total monthly credit allocation for the user's plan."""
        if not self._profile:
            return 0
        return self._profile.get("credits_monthly", 0)

    @property
    def email(self) -> str:
        """The authenticated user's email address."""
        if not self._profile:
            return ""
        return self._profile.get("email", "")

    @property
    def use_managed_credits(self) -> bool:
        """Determines if the proxy flow should be used."""
        return self.is_authenticated and self.user_plan in ("pro", "team", "enterprise")

    async def start_device_flow(self) -> Dict[str, Any]:
        """Starts the WorkOS device authorization flow."""
        return await self._device_client.start_flow(self._client_id)

    async def poll_device_flow(self, device_code: str) -> bool:
        """Polls for token and stores it if successful."""
        tokens = await self._device_client.poll_for_token(device_code)
        if tokens and tokens.get("access_token") and tokens.get("refresh_token"):
            KeyChainManager.set_auth_tokens(tokens["access_token"], tokens["refresh_token"])
            self._is_authenticated = True
            await self.fetch_user_profile()
            return True
        return False

    async def fetch_user_profile(self, _retried: bool = False) -> Dict[str, Any]:
        """Fetches the user profile from the backend API."""
        access_token, _ = KeyChainManager.get_auth_tokens()
        if not access_token:
            return {}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/user/me", headers={"Authorization": f"Bearer {access_token}"}
                )
                if response.status_code == 401:
                    if not _retried and await self.refresh_token():
                        return await self.fetch_user_profile(_retried=True)
                    else:
                        self.logout()
                        return {}

                response.raise_for_status()
                self._profile = response.json()
                return self._profile

            except httpx.HTTPError as e:
                logger.error(f"Failed to fetch user profile: {e}")
                return {}

    async def refresh_token(self) -> bool:
        """Refreshes the access token using the refresh token."""
        _, refresh_token = KeyChainManager.get_auth_tokens()
        if not refresh_token:
            self._is_authenticated = False
            return False

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/auth/token",
                    json={"grant_type": "refresh_token", "refresh_token": refresh_token},
                )
                if response.status_code == 200:
                    data = response.json()
                    KeyChainManager.set_auth_tokens(
                        data.get("access_token"),
                        data.get("refresh_token", refresh_token),
                    )
                    self._is_authenticated = True
                    return True
                else:
                    logger.warning(f"Token refresh failed: {response.text}")
                    self.logout()
                    return False
            except httpx.HTTPError as e:
                logger.error(f"Token refresh error: {e}")
                # Temporary network failure — don't log out, try again later
                return False

    def logout(self) -> None:
        """Logs the user out and clears tokens."""
        KeyChainManager.clear_auth_tokens()
        self._is_authenticated = False
        self._profile = None


