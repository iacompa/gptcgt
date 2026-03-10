from src.core.security import SecurityScanner


def test_security_scanner_scan_directory_detects_hardcoded_secret(tmp_path):
    """Directory-level security scans should flag obvious credential leaks."""
    project_root = tmp_path / "repo"
    project_root.mkdir()
    (project_root / "app.py").write_text('api_key = "sk-1234567890abcdef1234"\n', encoding="utf-8")

    scanner = SecurityScanner(project_root)
    findings = scanner.scan_directory(project_root)

    assert findings
    assert any(f.category == "secrets" and f.severity == "high" for f in findings)
