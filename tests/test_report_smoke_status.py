import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "report_smoke_status.py"
    spec = importlib.util.spec_from_file_location("report_smoke_status", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_should_notify_failure_only(monkeypatch):
    module = _load_module()
    monkeypatch.setenv("SMOKE_REPORT_SUITE", "API smoke")
    monkeypatch.setenv("SMOKE_REPORT_STATUS", "failure")
    monkeypatch.setenv("SMOKE_REPORT_ALERT_WEBHOOK_URL", "https://alerts.example.com")
    config = module.ReportConfig.from_env()

    assert module._should_notify(config) is True


def test_summary_includes_log_excerpt(tmp_path, monkeypatch):
    module = _load_module()
    log_path = tmp_path / "smoke.log"
    log_path.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")

    monkeypatch.setenv("SMOKE_REPORT_SUITE", "Web smoke")
    monkeypatch.setenv("SMOKE_REPORT_STATUS", "success")
    monkeypatch.setenv("SMOKE_REPORT_TARGET_URL", "https://gptcgt.ai")
    monkeypatch.setenv("SMOKE_REPORT_LOG_PATH", str(log_path))

    summary = module.render_summary(module.ReportConfig.from_env())

    assert "Web smoke" in summary
    assert "line 3" in summary
    assert "https://gptcgt.ai" in summary


def test_alert_payload_contains_run_url(monkeypatch):
    module = _load_module()
    monkeypatch.setenv("SMOKE_REPORT_SUITE", "API smoke")
    monkeypatch.setenv("SMOKE_REPORT_STATUS", "failure")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "iacompa/gptcgt")
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")

    payload = module._alert_payload(module.ReportConfig.from_env())

    assert payload["run_url"] == "https://github.com/iacompa/gptcgt/actions/runs/12345"
    assert "API smoke" in payload["text"]
