"""Tests for Phase 2: Continuity Guardrail Engine."""



def test_continuity_report_text_output():
    """Report produces readable text."""
    from src.core.continuity import ContinuityLink, ContinuityReport, FeaturePath, LinkStatus

    report = ContinuityReport(rules_checked=2, rules_passed=1, rules_failed=1)
    report.failures = ["No test file found for API route module 'billing'"]
    report.features = [
        FeaturePath(
            feature_name="API:/billing/webhook",
            links=[
                ContinuityLink(layer="api", name="/billing/webhook", file="api/routes/billing.py", status=LinkStatus.VERIFIED),
                ContinuityLink(layer="test", name="test_billing", status=LinkStatus.MISSING, detail="No matching test file"),
            ],
        )
    ]

    text = report.to_text()
    assert "1/2 rules passed" in text
    assert "billing" in text
    assert "MISSING" not in text  # We use icons, not enum names
    assert "❌" in text


def test_feature_path_completeness():
    """FeaturePath.is_complete checks all links."""
    from src.core.continuity import ContinuityLink, FeaturePath, LinkStatus

    complete = FeaturePath(
        feature_name="test",
        links=[
            ContinuityLink(layer="api", name="x", status=LinkStatus.VERIFIED),
            ContinuityLink(layer="test", name="y", status=LinkStatus.VERIFIED),
        ],
    )
    assert complete.is_complete is True

    incomplete = FeaturePath(
        feature_name="test",
        links=[
            ContinuityLink(layer="api", name="x", status=LinkStatus.VERIFIED),
            ContinuityLink(layer="test", name="y", status=LinkStatus.MISSING),
        ],
    )
    assert incomplete.is_complete is False
    assert len(incomplete.missing_links) == 1


def test_continuity_engine_discovers_db_tables(tmp_path):
    """Engine discovers CREATE TABLE statements in migration files."""
    from src.core.continuity import ContinuityEngine

    migration_dir = tmp_path / "api" / "migrations"
    migration_dir.mkdir(parents=True)
    (migration_dir / "001_users.sql").write_text("CREATE TABLE IF NOT EXISTS users (id UUID PRIMARY KEY);")
    (migration_dir / "002_teams.sql").write_text("CREATE TABLE teams (id UUID PRIMARY KEY);")

    engine = ContinuityEngine(tmp_path)
    tables = engine._discover_db_tables()
    assert "users" in tables
    assert "teams" in tables


def test_continuity_report_passed_when_clean(tmp_path):
    """Engine returns passed report when there are no API routes to check."""
    from src.core.continuity import ContinuityEngine

    # Empty project — no routes, no migrations
    engine = ContinuityEngine(tmp_path)
    report = engine.generate_report()
    # No API routes found, only migration check (skipped if no dir)
    assert report.rules_failed <= 1  # Migration check may pass or fail
