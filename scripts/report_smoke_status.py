#!/usr/bin/env python3
"""Emit workflow summaries and optional alerts for staging smoke runs."""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ReportConfig:
    suite: str
    status: str
    target_url: str
    details: str
    notify_on: str
    alert_webhook_url: str
    heartbeat_url: str
    failure_heartbeat_url: str
    log_path: str
    include_log_excerpt: bool

    @classmethod
    def from_env(cls) -> "ReportConfig":
        suite = os.getenv("SMOKE_REPORT_SUITE", "").strip() or "Staging Smoke"
        status = os.getenv("SMOKE_REPORT_STATUS", "").strip().lower() or "unknown"
        target_url = os.getenv("SMOKE_REPORT_TARGET_URL", "").strip()
        details = os.getenv("SMOKE_REPORT_DETAILS", "").strip()
        notify_on = os.getenv("SMOKE_REPORT_NOTIFY_ON", "failure").strip().lower() or "failure"
        if notify_on not in {"failure", "success", "always", "never"}:
            notify_on = "failure"
        return cls(
            suite=suite,
            status=status,
            target_url=target_url,
            details=details,
            notify_on=notify_on,
            alert_webhook_url=os.getenv("SMOKE_REPORT_ALERT_WEBHOOK_URL", "").strip(),
            heartbeat_url=os.getenv("SMOKE_REPORT_HEARTBEAT_URL", "").strip(),
            failure_heartbeat_url=os.getenv("SMOKE_REPORT_FAILURE_HEARTBEAT_URL", "").strip(),
            log_path=os.getenv("SMOKE_REPORT_LOG_PATH", "").strip(),
            include_log_excerpt=_env_bool("SMOKE_REPORT_INCLUDE_LOG_EXCERPT", True),
        )


def _github_run_url() -> str:
    server_url = os.getenv("GITHUB_SERVER_URL", "").strip()
    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    run_id = os.getenv("GITHUB_RUN_ID", "").strip()
    if server_url and repository and run_id:
        return f"{server_url}/{repository}/actions/runs/{run_id}"
    return ""


def _status_emoji(status: str) -> str:
    return {
        "success": "✅",
        "failure": "🚨",
        "cancelled": "🛑",
        "skipped": "⏭️",
    }.get(status, "ℹ️")


def _should_notify(config: ReportConfig) -> bool:
    if not config.alert_webhook_url:
        return False
    if config.notify_on == "always":
        return True
    if config.notify_on == "never":
        return False
    return config.status == config.notify_on


def _read_log_excerpt(log_path: str, max_lines: int = 20, max_chars: int = 4000) -> str:
    if not log_path:
        return ""
    path = Path(log_path)
    if not path.exists():
        return ""

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""

    excerpt = "\n".join(lines[-max_lines:])
    if len(excerpt) > max_chars:
        excerpt = excerpt[-max_chars:]
    return excerpt


def render_summary(config: ReportConfig) -> str:
    run_url = _github_run_url()
    lines = [
        f"## {_status_emoji(config.status)} {config.suite}",
        "",
        f"- Status: `{config.status}`",
    ]

    if config.target_url:
        lines.append(f"- Target: `{config.target_url}`")
    if run_url:
        lines.append(f"- Actions Run: {run_url}")
    if config.details:
        lines.append(f"- Details: {config.details}")

    excerpt = _read_log_excerpt(config.log_path) if config.include_log_excerpt else ""
    if excerpt:
        lines.extend(["", "### Log Tail", "", "```text", excerpt, "```"])

    lines.append("")
    return "\n".join(lines)


def _post_json(url: str, payload: dict) -> None:
    if not url:
        return
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=5) as response:  # noqa: S310
        response.read()


def _ping(url: str) -> None:
    if not url:
        return
    req = request.Request(url, method="GET")
    with request.urlopen(req, timeout=5) as response:  # noqa: S310
        response.read()


def _alert_payload(config: ReportConfig) -> dict:
    run_url = _github_run_url()
    text = f"{_status_emoji(config.status)} {config.suite} finished with status={config.status}"
    if config.target_url:
        text += f" for {config.target_url}"
    if run_url:
        text += f" | {run_url}"
    return {
        "text": text,
        "suite": config.suite,
        "status": config.status,
        "target_url": config.target_url,
        "details": config.details,
        "run_url": run_url,
        "repository": os.getenv("GITHUB_REPOSITORY", "").strip(),
        "workflow": os.getenv("GITHUB_WORKFLOW", "").strip(),
        "job": os.getenv("GITHUB_JOB", "").strip(),
    }


def main() -> int:
    config = ReportConfig.from_env()
    summary = render_summary(config)

    summary_path = os.getenv("GITHUB_STEP_SUMMARY", "").strip()
    if summary_path:
        Path(summary_path).write_text(summary, encoding="utf-8")
    else:
        print(summary)

    errors: list[str] = []

    try:
        if config.status == "success" and config.heartbeat_url:
            _ping(config.heartbeat_url)
        if config.status != "success" and config.failure_heartbeat_url:
            _ping(config.failure_heartbeat_url)
    except (OSError, error.URLError) as exc:
        errors.append(f"heartbeat failed: {exc}")

    try:
        if _should_notify(config):
            _post_json(config.alert_webhook_url, _alert_payload(config))
    except (OSError, error.URLError) as exc:
        errors.append(f"alert webhook failed: {exc}")

    if errors:
        for item in errors:
            print(f"[smoke-report] {item}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
