#!/usr/bin/env python3
"""Manual staging smoke runner for real external-service checks."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

GITHUB_AUTH_PREFIX = "https://github.com/login/oauth/authorize"
STRIPE_CHECKOUT_PREFIX = "https://checkout.stripe.com/"


class SmokeFailure(RuntimeError):
    """Raised when a smoke assertion fails."""


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SmokeFailure(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class SmokeConfig:
    api_url: str
    auth_token: str
    expect_github_connected: bool
    allow_github_disconnect: bool
    run_checkout_smoke: bool
    checkout_plan: str
    checkout_annual: bool
    credit_purchase_amount: int
    run_webhook_smoke: bool
    stripe_webhook_secret: str | None
    run_hub_smoke: bool
    hub_repo_url: str | None
    hub_prompt: str | None
    hub_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "SmokeConfig":
        api_url = _require_env("SMOKE_API_URL").rstrip("/")
        auth_token = _require_env("SMOKE_AUTH_TOKEN")
        run_checkout_smoke = not _env_bool("SMOKE_SKIP_CHECKOUT", False)
        run_webhook_smoke = _env_bool("SMOKE_RUN_WEBHOOK_SMOKE", False)
        run_hub_smoke = _env_bool("SMOKE_RUN_HUB_SMOKE", False)
        stripe_webhook_secret = os.getenv("SMOKE_STRIPE_WEBHOOK_SECRET", "").strip() or None
        hub_repo_url = os.getenv("SMOKE_HUB_REPO_URL", "").strip() or None
        hub_prompt = os.getenv("SMOKE_HUB_PROMPT", "").strip() or None

        if run_webhook_smoke and not stripe_webhook_secret:
            raise SmokeFailure("SMOKE_RUN_WEBHOOK_SMOKE requires SMOKE_STRIPE_WEBHOOK_SECRET")

        if run_hub_smoke:
            if not hub_repo_url:
                raise SmokeFailure("SMOKE_RUN_HUB_SMOKE requires SMOKE_HUB_REPO_URL")
            if not hub_prompt:
                raise SmokeFailure("SMOKE_RUN_HUB_SMOKE requires SMOKE_HUB_PROMPT")

        return cls(
            api_url=api_url,
            auth_token=auth_token,
            expect_github_connected=_env_bool("SMOKE_EXPECT_GITHUB_CONNECTED", False),
            allow_github_disconnect=_env_bool("SMOKE_ALLOW_GITHUB_DISCONNECT", False),
            run_checkout_smoke=run_checkout_smoke,
            checkout_plan=os.getenv("SMOKE_CHECKOUT_PLAN", "pro").strip() or "pro",
            checkout_annual=_env_bool("SMOKE_CHECKOUT_ANNUAL", False),
            credit_purchase_amount=int(os.getenv("SMOKE_CREDIT_PURCHASE_AMOUNT", "100")),
            run_webhook_smoke=run_webhook_smoke,
            stripe_webhook_secret=stripe_webhook_secret,
            run_hub_smoke=run_hub_smoke,
            hub_repo_url=hub_repo_url,
            hub_prompt=hub_prompt,
            hub_timeout_seconds=max(30, int(os.getenv("SMOKE_HUB_TIMEOUT_SECONDS", "240"))),
        )


def _log(step: str, message: str) -> None:
    print(f"[staging-smoke] {step}: {message}")


def _exc_detail(exc: BaseException) -> str:
    detail = str(exc).strip()
    return detail or repr(exc)


def _stripe_signature(payload: bytes, secret: str) -> str:
    try:
        import stripe
    except ImportError as exc:  # pragma: no cover - exercised in staging only
        raise SmokeFailure("stripe is required when SMOKE_RUN_WEBHOOK_SMOKE is enabled") from exc

    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
    signature = stripe.WebhookSignature._compute_signature(signed_payload, secret)
    return f"t={timestamp},v1={signature}"


def _build_noop_webhook_payload() -> bytes:
    payload = {
        "id": f"evt_smoke_{uuid4().hex}",
        "object": "event",
        "type": "smoke.noop",
        "data": {"object": {"id": f"obj_smoke_{uuid4().hex}"}},
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


async def _request_json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    expected_status: int = 200,
    **kwargs: Any,
) -> Any:
    _log("request", f"{method} {path}")
    try:
        response = await client.request(method, path, **kwargs)
    except httpx.TimeoutException as exc:
        raise SmokeFailure(f"{method} {path} timed out: {_exc_detail(exc)}") from exc
    except httpx.HTTPError as exc:
        raise SmokeFailure(f"{method} {path} transport failed: {_exc_detail(exc)}") from exc
    except OSError as exc:
        raise SmokeFailure(f"{method} {path} OS error: {_exc_detail(exc)}") from exc
    if response.status_code != expected_status:
        detail = response.text.strip() or f"unexpected status {response.status_code}"
        raise SmokeFailure(f"{method} {path} failed: {response.status_code} {detail}")
    if not response.text:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise SmokeFailure(f"{method} {path} returned invalid JSON: {_exc_detail(exc)}") from exc


async def _check_health(client: httpx.AsyncClient) -> None:
    payload = await _request_json(client, "GET", "/health")
    if payload.get("status") != "ok":
        raise SmokeFailure(f"/health returned unexpected payload: {payload}")
    _log("health", "ok")


async def _check_billing(client: httpx.AsyncClient, config: SmokeConfig) -> None:
    status = await _request_json(client, "GET", "/billing/status")
    required_keys = {"plan", "credits_remaining", "subscription_status", "billing_access"}
    if not required_keys.issubset(status):
        raise SmokeFailure(f"/billing/status missing required keys: {status}")
    _log("billing", f"status ok (plan={status['plan']}, billing_access={status['billing_access']})")

    if not config.run_checkout_smoke:
        return

    checkout = await _request_json(
        client,
        "POST",
        "/billing/checkout",
        json={"plan": config.checkout_plan, "annual": config.checkout_annual, "quantity": 1},
    )
    checkout_url = str(checkout.get("url", ""))
    if not checkout_url.startswith(STRIPE_CHECKOUT_PREFIX):
        raise SmokeFailure(f"/billing/checkout returned unexpected URL: {checkout_url}")
    _log("billing", f"subscription checkout ok ({config.checkout_plan})")

    credits = await _request_json(
        client,
        "POST",
        "/billing/credits",
        json={"credit_amount": config.credit_purchase_amount},
    )
    credit_url = str(credits.get("url", ""))
    if not credit_url.startswith(STRIPE_CHECKOUT_PREFIX):
        raise SmokeFailure(f"/billing/credits returned unexpected URL: {credit_url}")
    _log("billing", f"credit checkout ok ({config.credit_purchase_amount} credits)")


async def _check_github(client: httpx.AsyncClient, config: SmokeConfig) -> None:
    status = await _request_json(client, "GET", "/github/status")
    connected = bool(status.get("connected"))
    if config.expect_github_connected and not connected:
        raise SmokeFailure("GitHub is expected to be connected for this smoke run, but /github/status returned false")
    _log("github", f"status ok (connected={connected})")

    connect = await _request_json(client, "GET", "/github/connect")
    auth_url = str(connect.get("auth_url", ""))
    if not auth_url.startswith(GITHUB_AUTH_PREFIX):
        raise SmokeFailure(f"/github/connect returned unexpected auth URL: {auth_url}")
    _log("github", "connect URL ok")

    if config.allow_github_disconnect:
        if not connected:
            raise SmokeFailure("SMOKE_ALLOW_GITHUB_DISCONNECT requires a connected GitHub account")
        await _request_json(client, "POST", "/github/disconnect")
        disconnected = await _request_json(client, "GET", "/github/status")
        if disconnected.get("connected") is not False:
            raise SmokeFailure("/github/disconnect did not clear the integration")
        _log("github", "disconnect ok")


async def _check_webhook(client: httpx.AsyncClient, config: SmokeConfig) -> None:
    if not config.run_webhook_smoke or not config.stripe_webhook_secret:
        return

    payload = _build_noop_webhook_payload()
    signature = _stripe_signature(payload, config.stripe_webhook_secret)
    response = await _request_json(
        client,
        "POST",
        "/billing/webhook",
        content=payload,
        headers={"stripe-signature": signature, "Content-Type": "application/json"},
    )
    if response.get("status") != "ok":
        raise SmokeFailure(f"/billing/webhook returned unexpected payload: {response}")
    _log("stripe", "signed webhook ok")


async def _stream_hub_status(
    client: httpx.AsyncClient,
    run_id: str,
    timeout_seconds: int,
) -> tuple[str | None, list[str]]:
    status: str | None = None
    log_tail: list[str] = []
    async with asyncio.timeout(timeout_seconds):
        async with client.stream("GET", f"/hub/{run_id}/logs") as response:
            if response.status_code != 200:
                detail = (await response.aread()).decode("utf-8", errors="replace")
                raise SmokeFailure(f"GET /hub/{run_id}/logs failed: {response.status_code} {detail}")

            current_event = "message"
            async for line in response.aiter_lines():
                if not line:
                    current_event = "message"
                    continue
                if line.startswith("event: "):
                    current_event = line.split(": ", 1)[1]
                    continue
                if not line.startswith("data: "):
                    continue

                data = line[6:]
                if data == "[DONE]":
                    break

                if current_event == "status":
                    payload = json.loads(data)
                    status = payload.get("status")
                    continue

                log_tail.append(data)
                if len(log_tail) > 20:
                    log_tail = log_tail[-20:]

    return status, log_tail


async def _check_hub(client: httpx.AsyncClient, config: SmokeConfig) -> None:
    if not config.run_hub_smoke or not config.hub_repo_url or not config.hub_prompt:
        return

    created = await _request_json(
        client,
        "POST",
        "/hub",
        json={"repo_url": config.hub_repo_url, "prompt": config.hub_prompt},
    )
    run_id = str(created.get("id", "")).strip()
    if not run_id:
        raise SmokeFailure(f"/hub did not return a run id: {created}")
    _log("hub", f"run queued ({run_id})")

    status, log_tail = await _stream_hub_status(client, run_id, config.hub_timeout_seconds)
    if status != "completed":
        joined_tail = "\n".join(log_tail[-10:])
        raise SmokeFailure(f"Hub run {run_id} finished with status={status!r}\nRecent log tail:\n{joined_tail}")
    _log("hub", f"run completed ({run_id})")


async def _run() -> None:
    config = SmokeConfig.from_env()
    _log(
        "config",
        (
            f"api={config.api_url} "
            f"checkout={config.run_checkout_smoke} "
            f"webhook={config.run_webhook_smoke} "
            f"hub={config.run_hub_smoke}"
        ),
    )
    headers = {"Authorization": f"Bearer {config.auth_token}"}
    timeout = httpx.Timeout(connect=15.0, read=45.0, write=30.0, pool=30.0)
    async with httpx.AsyncClient(base_url=config.api_url, headers=headers, timeout=timeout, follow_redirects=False) as client:
        await _check_health(client)
        await _check_billing(client, config)
        await _check_github(client, config)
        await _check_webhook(client, config)
        await _check_hub(client, config)


def main() -> int:
    try:
        asyncio.run(_run())
    except SmokeFailure as exc:
        _log("failure", str(exc))
        return 1
    except KeyboardInterrupt:
        _log("failure", "Interrupted")
        return 130
    except Exception as exc:  # pragma: no cover - last-resort crash path
        _log("failure", f"Unexpected crash: {_exc_detail(exc)}")
        return 1

    _log("summary", "all requested staging smoke checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
