import os

import asyncpg
import pytest

from api.migrations.run_migration import run_migration


@pytest.mark.asyncio
async def test_canonical_schema_migration_integrity(monkeypatch):
    """
    Spins up a throwaway test database, runs the exact canonical migration
    runner script, and asserts that crucial tables (users, teams) exist
    and contain the expected Python-used columns without throwing errors.
    """
    base_url = os.environ.get("DATABASE_URL")
    if not base_url or "sqlite" in base_url or "memory" in base_url:
        pytest.skip("DATABASE_URL not appropriate. Skipping real DB integration test.")

    if "_test" not in base_url and "-test" not in base_url:
        pytest.skip("DATABASE_URL does not contain '_test' or '-test'. Skipping destructive migration test for safety.")

    conn = await asyncpg.connect(base_url)
    try:
        # P1-06: Isolate DB state by wiping existing tables in the schema
        await conn.execute(
            "DROP TABLE IF EXISTS device_auth_sessions, team_members, api_keys, usage_logs, usage_events, "
            "audit_log, conversations, pending_deductions, webhook_events, team_invites, hub_runs, users, teams CASCADE;"
        )
    finally:
        await conn.close()

    # Run the exact canonical migration runner script
    await run_migration()

    # Verify tables generated correctly
    conn = await asyncpg.connect(base_url)
    try:
        # Check users table columns
        user_cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")
        cols = {r["column_name"] for r in user_cols}

        assert "password_hash" in cols, "canonical schema missed password_hash"
        assert "overage_enabled" in cols, "canonical schema missed overage_enabled"
        assert "team_id" in cols, "canonical schema missed team_id"
        assert "allocated_quota" in cols, "canonical schema missed allocated_quota"

        # Check new github columns (007)
        assert "github_username" in cols, "canonical schema missed github_username"
        assert "github_token" in cols, "canonical schema missed github_token"

        # Check teams table constrains relaxing allows free plans
        team_cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'teams'")
        tcols = {r["column_name"] for r in team_cols}
        assert "seats_purchased" in tcols

        # Check team_invites table (008) exists
        invite_cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'team_invites'")
        icols = {r["column_name"] for r in invite_cols}
        assert "email" in icols
        assert "invited_by" in icols

        # Check hub_runs table (010) exists
        hub_cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'hub_runs'")
        hcols = {r["column_name"] for r in hub_cols}
        assert "repo_url" in hcols
        assert "task_prompt" in hcols
        assert "status" in hcols
        assert "logs" in hcols
        assert "workspace_path" in hcols
        assert "head_branch" in hcols
        assert "base_branch" in hcols

        device_cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'device_auth_sessions'"
        )
        dcols = {r["column_name"] for r in device_cols}
        assert "device_code_hash" in dcols
        assert "user_code" in dcols
        assert "encrypted_refresh_token" in dcols

    finally:
        await conn.close()
