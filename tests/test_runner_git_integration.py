import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from api.services.runner import runner


def _git(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


@pytest.mark.asyncio
async def test_runner_pushes_to_local_bare_origin(tmp_path):
    origin = tmp_path / "origin.git"
    seed = tmp_path / "seed"

    _git("init", "--bare", str(origin))
    _git("init", str(seed))
    _git("checkout", "-b", "main", cwd=seed)
    _git("config", "user.name", "Test User", cwd=seed)
    _git("config", "user.email", "test@example.com", cwd=seed)
    (seed / "README.md").write_text("seed\n")
    _git("add", "README.md", cwd=seed)
    _git("commit", "-m", "Initial commit", cwd=seed)
    _git("remote", "add", "origin", str(origin), cwd=seed)
    _git("push", "-u", "origin", "main", cwd=seed)

    run_id = uuid4()
    str_run_id = str(run_id)

    try:
        workspace, base_branch = await runner._prepare_workspace(
            str_run_id,
            str(origin),
            None,
            "gptcgt-auto-test",
        )
        assert base_branch == "main"

        (workspace / "CHANGELOG.md").write_text("Hub change\n")
        success, message = await runner._finalize_git_changes(str_run_id, run_id)

        assert success is True
        assert "pushed branch gptcgt-auto-test" in message.lower()

        pushed_ref = _git("--git-dir", str(origin), "rev-parse", "refs/heads/gptcgt-auto-test")
        workspace_ref = _git("rev-parse", "HEAD", cwd=workspace)
        assert pushed_ref == workspace_ref
    finally:
        runner._cleanup_workspace(str_run_id)


@pytest.mark.asyncio
async def test_prepare_workspace_rewrites_github_remote_without_token(monkeypatch, tmp_path):
    run_id = str(uuid4())
    commands: list[tuple[str, ...]] = []
    responses = iter(
        [
            (0, "cloned"),
            (0, ""),
            (0, "main\n"),
            (0, ""),
        ]
    )

    async def fake_run_command(*cmd, **kwargs):
        commands.append(tuple(cmd))
        return next(responses)

    monkeypatch.setattr(runner, "_run_command", fake_run_command)

    await runner._prepare_workspace(
        run_id,
        "https://github.com/octocat/hello-world",
        "ghs_secret",
        "gptcgt-auto-test",
    )

    clone_command = commands[0]
    set_url_command = commands[1]
    assert "x-access-token:ghs_secret@github.com/octocat/hello-world.git" in clone_command[4]
    assert set_url_command[0:2] == ("git", "-C")
    assert set_url_command[3:] == (
        "remote",
        "set-url",
        "origin",
        "https://github.com/octocat/hello-world.git",
    )
    assert runner._run_context[run_id]["github_token"] == "ghs_secret"
    runner._cleanup_workspace(run_id)
