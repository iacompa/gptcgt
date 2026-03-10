import asyncio
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from api.services.runner import runner


@pytest.fixture
async def mock_auth(monkeypatch):
    """Mock out get_current_user to bypass WorkOS locally."""
    user_id = str(uuid4())

    async def mock_get_current_user():
        return user_id

    # The actual FastAPI dependency override is the absolute most reliable method
    from api.routes.hub import get_current_user
    app.dependency_overrides[get_current_user] = mock_get_current_user

    # We must ALSO bypass AuthMiddleware. The easiest way without starting a live server
    # is to monkeypatch the AuthMiddleware dispatch early exit for our test paths
    from api.middleware.auth import AuthMiddleware
    original_dispatch = AuthMiddleware.dispatch

    async def mock_dispatch(self, request, call_next):
        if request.url.path.startswith("/hub"):
            request.state.user_id = user_id
            return await call_next(request)
        return await original_dispatch(self, request, call_next)

    monkeypatch.setattr(AuthMiddleware, "dispatch", mock_dispatch)

    return user_id

@pytest.fixture
async def mock_db(monkeypatch, mock_auth):
    """Mock the asyncpg pool interactions for the tests."""
    class MockPool:
        def __init__(self):
            self.logs = {}
            self.statuses = {}

        async def fetchval(self, query, *args):
            # If we're checking owner, return the mock user
            if "SELECT status FROM hub_runs WHERE id" in query:
                return self.statuses.get(str(args[0]))
            if "FROM hub_runs WHERE id" in query and "logs" not in query:
                return mock_auth
            if "github_token FROM users WHERE id" in query:
                return "pt:fake_encryption_string"
            if "SELECT logs FROM hub_runs WHERE id" in query:
                return self.logs.get(str(args[0]), "")
            # Otherwise return a generic run token or key
            return uuid4()

        async def execute(self, query, *args):
            if "UPDATE hub_runs SET logs" in query:
                run_id = str(args[1])
                line = args[0]
                if run_id not in self.logs:
                    self.logs[run_id] = ""
                self.logs[run_id] += line
                return

            if "UPDATE hub_runs SET status = $1" in query:
                self.statuses[str(args[1])] = args[0]
                return

            if "SET status = 'running'" in query:
                self.statuses[str(args[0])] = "running"
                return

            if "SET status = 'failed'" in query:
                self.statuses[str(args[0])] = "failed"
                return

            if "SET status = 'cancelled'" in query:
                self.statuses[str(args[0])] = "cancelled"

        async def fetchrow(self, query, *args):
            return {
                "user_id": mock_auth,
                "repo_url": "https://github.com/test/repo",
                "status": "completed",
                "workspace_path": "/tmp/mock_workspace",
                "head_branch": "gptcgt-auto-test",
                "base_branch": "main",
            }

    pool = MockPool()
    monkeypatch.setattr("api.routes.hub.get_pool", lambda: pool)
    monkeypatch.setattr("api.services.runner.get_pool", lambda: pool)
    return pool

@pytest.mark.asyncio
async def test_runner_singleton_lifecycle(mock_db, monkeypatch, tmp_path):
    """Test that the RunManager singleton can capture and cancel fake process output."""
    run_id = uuid4()

    class FakeStdout:
        def __init__(self):
            self._lines = [b"booting\n"]
            self._done = asyncio.Event()

        async def readline(self):
            if self._lines:
                return self._lines.pop(0)
            await self._done.wait()
            return b""

        def finish(self):
            self._done.set()

    class FakeProcess:
        def __init__(self):
            self.stdout = FakeStdout()
            self.returncode = None
            self._done = asyncio.Event()

        async def wait(self):
            await self._done.wait()
            return self.returncode

        def terminate(self):
            self.returncode = 0
            self.stdout.finish()
            self._done.set()

    async def fake_prepare_workspace(str_run_id, repo_url, github_token, head_branch):
        runner._run_context[str_run_id] = {
            "workspace_path": str(tmp_path),
            "head_branch": head_branch,
            "base_branch": "main",
        }
        return tmp_path, "main"

    async def fake_spawn(*args, **kwargs):
        return FakeProcess()

    monkeypatch.setattr(runner, "_prepare_workspace", fake_prepare_workspace)
    monkeypatch.setattr("api.services.runner.asyncio.create_subprocess_exec", fake_spawn)

    # This will spawn a dummy python process that just echoes and sleeps
    await runner.start_run(run_id, uuid4(), "test-repo", "test-prompt")

    # Check that it's physically tracked
    assert str(run_id) in runner._processes

    # Log stream should be yielding
    iterator = runner.get_log_iterator(str(run_id))
    first_chunk = await anext(iterator)
    assert "data: Initializing run" in first_chunk

    # Cancel it
    success = await runner.cancel_run(run_id)
    assert success is True

    # Wait for the cancellation to propagate to the process
    await asyncio.sleep(0.1)
    assert mock_db.statuses[str(run_id)] == "cancelled"
    assert str(run_id) not in runner._processes
    assert str(run_id) not in runner._temp_workspaces


@pytest.mark.asyncio
async def test_runner_redacts_github_token_in_push_failures(monkeypatch, tmp_path):
    run_id = uuid4()
    str_run_id = str(run_id)
    secret = "ghs_test_secret"

    runner._run_context[str_run_id] = {
        "workspace_path": str(tmp_path),
        "head_branch": "gptcgt-auto-test",
        "base_branch": "main",
        "redact_secret": secret,
    }

    responses = iter(
        [
            (0, " M changed.py\n"),
            (0, ""),
            (0, ""),
            (0, ""),
            (0, ""),
            (0, f"https://x-access-token:{secret}@github.com/test/repo.git"),
            (1, f"fatal: could not read https://x-access-token:{secret}@github.com/test/repo.git"),
        ]
    )

    async def fake_run_command(*args, **kwargs):
        return next(responses)

    monkeypatch.setattr(runner, "_run_command", fake_run_command)

    success, message = await runner._finalize_git_changes(str_run_id, run_id)
    assert success is False
    assert secret not in message
    assert "***" in message
    runner._run_context.pop(str_run_id, None)

@pytest.mark.asyncio
async def test_hub_run_creation(mock_auth, mock_db):
    """Test POST /api/hub/runs kicks off the process and returns the ID."""
    original_start_run = runner.start_run
    runner.start_run = AsyncMock()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Mock the DB so it thinks the user has a GitHub token
            response = await client.post(
                "/hub",
                json={"repo_url": "https://github.com/t/test", "prompt": "Fix bug"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert data["status"] == "queued"
    finally:
        runner.start_run = original_start_run


@pytest.mark.asyncio
async def test_hub_run_creation_allows_local_repo_without_github_token(mock_auth, monkeypatch, tmp_path):
    class LocalOnlyPool:
        async def fetchval(self, query, *args):
            if "github_token FROM users WHERE id" in query:
                raise AssertionError("local repos should not require github_token")
            return uuid4()

    monkeypatch.setattr("api.routes.hub.get_pool", lambda: LocalOnlyPool())

    original_start_run = runner.start_run
    runner.start_run = AsyncMock()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/hub",
                json={"repo_url": str(tmp_path), "prompt": "Fix local bug"},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "queued"
    finally:
        runner.start_run = original_start_run

@pytest.mark.asyncio
async def test_hub_run_cancel(mock_auth, mock_db):
    """Test the POST cancel endpoint parses correctly."""
    run_id = uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/hub/{run_id}/cancel")
        assert response.status_code in (200, 400)  # Either succeeds or graceful fail if proc didn't exist


@pytest.mark.asyncio
async def test_log_iterator_emits_terminal_status_event(mock_db):
    run_id = uuid4()
    str_run_id = str(run_id)
    mock_db.logs[str_run_id] = "booting\n"
    mock_db.statuses[str_run_id] = "failed"
    runner._completion_events[str_run_id] = asyncio.Event()
    runner._completion_events[str_run_id].set()
    runner._log_events[str_run_id] = asyncio.Event()

    try:
        chunks = []
        async for chunk in runner.get_log_iterator(str_run_id):
            chunks.append(chunk)
    finally:
        runner._completion_events.pop(str_run_id, None)
        runner._log_events.pop(str_run_id, None)

    assert any("event: status" in chunk and '"failed"' in chunk for chunk in chunks)


@pytest.mark.asyncio
async def test_hub_run_pr_generation_mock(mock_auth, mock_db, monkeypatch):
    """Test that /pr correctly requests to generate a PR for completed runs."""

    # Mock the github library
    class MockRepo:
        def create_pull(self, **kwargs):
            class MockPR:
                html_url = "https://github.com/t/test/pull/1"
            return MockPR()

    class MockGithub:
        def __init__(self, token):
            pass
        def get_repo(self, repo_name):
            return MockRepo()

    import sys
    import types
    if "github" not in sys.modules:
        sys.modules["github"] = types.ModuleType("github")

    monkeypatch.setattr("github.Github", MockGithub, raising=False)
    monkeypatch.setattr("api.routes.github._decrypt_token", lambda *args: "fake_gh_token", raising=False)

    # Bypass Phase 1 ProofRunner / ProofValidator gate for this mock test
    from src.core.proof import ProofBundle, ProofRunner, ProofValidator, Verdict
    mock_bundle = ProofBundle()
    mock_bundle.verdict = Verdict.VERIFIED
    mock_bundle.summary = "Mock proof: all checks passed"

    def fake_run_all(self, **kwargs):
        assert self.project_root == Path("/tmp/mock_workspace")
        return mock_bundle

    monkeypatch.setattr(ProofRunner, "run_all", fake_run_all)
    monkeypatch.setattr(ProofValidator, "validate", staticmethod(lambda bundle: (True, None)))

    run_id = uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/hub/{run_id}/pr")
        assert response.status_code == 200
        assert response.json()["pr_url"] == "https://github.com/t/test/pull/1"
