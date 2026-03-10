import asyncio
import base64
import json
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

from api.database import get_pool

logger = logging.getLogger(__name__)


class RunManager:
    """
    Manages the lifecycle of background Hub runs.
    Keeps track of active gptcgt subprocesses and buffers their stdout/stderr
    for real-time streaming to the frontend.
    """

    def __init__(self):
        # run_id -> Process
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        # run_id -> asyncio.Event (fired when process completes)
        self._completion_events: dict[str, asyncio.Event] = {}
        # run_id -> asyncio.Event (fired when new log content is available)
        self._log_events: dict[str, asyncio.Event] = {}
        # run_id -> temp workspace path
        self._temp_workspaces: dict[str, Path] = {}
        # run_id -> branch metadata needed after process exit
        self._run_context: dict[str, dict[str, str]] = {}
        # run_id values explicitly cancelled by the user
        self._cancelled_runs: set[str] = set()

    def _sanitize_output(self, output: str, secret: str | None = None) -> str:
        if secret:
            output = output.replace(secret, "***")
        return output.strip()

    @staticmethod
    def _build_github_push_header(github_token: str) -> str:
        credentials = base64.b64encode(f"x-access-token:{github_token}".encode("utf-8")).decode("ascii")
        return f"AUTHORIZATION: basic {credentials}"

    async def _should_push_remote(self, remote_url: str) -> tuple[bool, str | None]:
        remote_url = remote_url.strip()
        if "github.com" in remote_url:
            return True, None

        remote_path: Path | None = None
        parsed = urlparse(remote_url)
        if parsed.scheme == "file":
            remote_path = Path(parsed.path)
        else:
            candidate = Path(remote_url).expanduser()
            if candidate.exists():
                remote_path = candidate

        if not remote_path:
            return False, f"Committed changes locally; origin push skipped for unsupported remote '{remote_url}'."

        code, output = await self._run_command(
            "git",
            "-C",
            str(remote_path),
            "rev-parse",
            "--is-bare-repository",
        )
        if code != 0:
            return False, f"Committed changes locally; origin push skipped because remote inspection failed: {self._sanitize_output(output)}"  # noqa: E501

        if output.strip().lower() == "true":
            return True, None

        return False, "Committed changes locally; origin push skipped for non-bare local remote."

    async def _run_command(
        self,
        *cmd: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd) if cwd else None,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace") if stdout else ""
        return proc.returncode, output

    async def _prepare_workspace(
        self,
        str_run_id: str,
        repo_url: str,
        github_token: str | None,
        head_branch: str,
    ) -> tuple[Path, str]:
        """Clone the target repo into a scratch workspace and create the Hub branch."""
        workspace = Path(tempfile.mkdtemp(prefix=f"hub-run-{str_run_id[:8]}-"))
        self._temp_workspaces[str_run_id] = workspace

        candidate = Path(repo_url).expanduser()
        clone_source = str(candidate.resolve()) if candidate.exists() and candidate.is_dir() else None
        token_to_redact = None

        if not clone_source:
            from api.routes.github import _repo_name_from_url

            repo_name = _repo_name_from_url(repo_url)
            if not github_token:
                raise RuntimeError("GitHub token missing for remote repository clone")
            token_to_redact = github_token
            clone_source = f"https://x-access-token:{github_token}@github.com/{repo_name}.git"
            public_remote_url = f"https://github.com/{repo_name}.git"
        else:
            public_remote_url = clone_source

        code, output = await self._run_command("git", "clone", "--depth", "1", clone_source, str(workspace))
        if code != 0:
            raise RuntimeError(f"git clone failed: {self._sanitize_output(output, token_to_redact)}")

        if token_to_redact:
            code, output = await self._run_command(
                "git",
                "-C",
                str(workspace),
                "remote",
                "set-url",
                "origin",
                public_remote_url,
            )
            if code != 0:
                raise RuntimeError(f"git remote set-url failed: {self._sanitize_output(output, token_to_redact)}")

        code, base_branch = await self._run_command("git", "-C", str(workspace), "rev-parse", "--abbrev-ref", "HEAD")
        if code != 0 or not base_branch.strip():
            raise RuntimeError(f"failed to determine base branch: {self._sanitize_output(base_branch)}")
        base_branch = base_branch.strip()

        code, output = await self._run_command("git", "-C", str(workspace), "checkout", "-b", head_branch)
        if code != 0:
            raise RuntimeError(f"git checkout -b failed: {self._sanitize_output(output)}")

        self._run_context[str_run_id] = {
            "workspace_path": str(workspace),
            "head_branch": head_branch,
            "base_branch": base_branch,
            "redact_secret": token_to_redact or "",
            "github_token": github_token or "",
        }
        return workspace, base_branch

    async def _finalize_git_changes(self, str_run_id: str, run_id: UUID) -> tuple[bool, str]:
        context = self._run_context.get(str_run_id)
        if not context:
            return False, "Run workspace context missing."

        workspace = Path(context["workspace_path"])
        head_branch = context["head_branch"]
        redact_secret = context.get("redact_secret") or None
        github_token = context.get("github_token") or None

        code, output = await self._run_command("git", "-C", str(workspace), "status", "--porcelain")
        if code != 0:
            return False, f"git status failed: {self._sanitize_output(output, redact_secret)}"
        if not output.strip():
            return False, "No file changes were produced by the autonomous run."

        commands = [
            ("git", "-C", str(workspace), "config", "user.name", "GPTCGT Hub"),
            ("git", "-C", str(workspace), "config", "user.email", "hub@gptcgt.ai"),
            ("git", "-C", str(workspace), "add", "-A"),
            ("git", "-C", str(workspace), "commit", "-m", f"Hub run {run_id}"),
        ]
        for command in commands:
            code, output = await self._run_command(*command)
            if code != 0:
                return False, f"{command[0]} step failed: {self._sanitize_output(output, redact_secret)}"

        code, remote_url = await self._run_command("git", "-C", str(workspace), "remote", "get-url", "origin")
        if code != 0:
            return False, f"git remote lookup failed: {self._sanitize_output(remote_url, redact_secret)}"

        remote_url = remote_url.strip()
        should_push, skip_message = await self._should_push_remote(remote_url)
        if not should_push:
            return True, skip_message or f"Committed changes on {head_branch}; origin push skipped."

        push_command = ["git", "-C", str(workspace)]
        if github_token and "github.com" in remote_url:
            push_command.extend(["-c", f"http.extraheader={self._build_github_push_header(github_token)}"])
        push_command.extend(["push", "-u", "origin", head_branch])

        code, output = await self._run_command(*push_command)
        if code != 0:
            return False, f"git push failed: {self._sanitize_output(output, redact_secret)}"

        return True, f"Committed and pushed branch {head_branch}."

    def _cleanup_workspace(self, str_run_id: str) -> None:
        workspace = self._temp_workspaces.pop(str_run_id, None)
        if workspace and workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)
        self._run_context.pop(str_run_id, None)
        self._completion_events.pop(str_run_id, None)
        self._log_events.pop(str_run_id, None)
        self._cancelled_runs.discard(str_run_id)

    async def start_run(self, run_id: UUID, user_id: UUID, repo_url: str, prompt: str) -> None:
        """Spawn the background agent execution and pipe logs into Postgres."""
        str_run_id = str(run_id)
        repo_root = Path(__file__).resolve().parents[2]
        head_branch = f"gptcgt-auto-{str_run_id[:8]}"

        self._completion_events[str_run_id] = asyncio.Event()
        self._log_events[str_run_id] = asyncio.Event()

        # Update DB to 'running'
        pool = get_pool()
        await pool.execute(
            "UPDATE hub_runs SET status = 'running', logs = '', updated_at = now() WHERE id = $1",
            run_id
        )

        # In production this would clone the repo to a scratch dir.
        # For P1-09 completeness, we invoke the python module autonomously.
        await self._append_log(pool, run_id, f"Initializing run {run_id} for {repo_url}...\n")
        github_token: str | None = None
        repo_candidate = Path(repo_url).expanduser()

        if not (repo_candidate.exists() and repo_candidate.is_dir()):
            encrypted_token = await pool.fetchval("SELECT github_token FROM users WHERE id = $1", user_id)
            if not encrypted_token:
                await pool.execute(
                    "UPDATE hub_runs SET status = 'failed', updated_at = now() WHERE id = $1",
                    run_id,
                )
                await self._append_log(pool, run_id, "CRITICAL RUNNER ERROR: GitHub token missing.\n")
                self._completion_events[str_run_id].set()
                return

            from api.routes.github import _decrypt_token

            try:
                github_token = _decrypt_token(encrypted_token)
            except Exception as e:
                await self._append_log(pool, run_id, f"CRITICAL RUNNER ERROR: {e}\n")
                await pool.execute(
                    "UPDATE hub_runs SET status = 'failed', updated_at = now() WHERE id = $1",
                    run_id,
                )
                self._completion_events[str_run_id].set()
                return

        try:
            workspace_path, base_branch = await self._prepare_workspace(str_run_id, repo_url, github_token, head_branch)
        except Exception as e:
            logger.error(f"Failed to prepare workspace for {run_id}: {e}")
            await self._append_log(pool, run_id, f"CRITICAL RUNNER ERROR: {e}\n")
            await pool.execute(
                "UPDATE hub_runs SET status = 'failed', updated_at = now() WHERE id = $1",
                run_id,
            )
            self._completion_events[str_run_id].set()
            self._cleanup_workspace(str_run_id)
            return

        await pool.execute(
            """
            UPDATE hub_runs
            SET workspace_path = $1, head_branch = $2, base_branch = $3, updated_at = now()
            WHERE id = $4
            """,
            str(workspace_path),
            head_branch,
            base_branch,
            run_id,
        )
        await self._append_log(pool, run_id, f"Workspace ready at {workspace_path} on {base_branch} -> {head_branch}.\n")

        cmd = [
            sys.executable,
            "-m",
            "src.tui.app",
            "--workspace",
            str(workspace_path),
            "--autonomous-goal",
            prompt,
            "--headless",
        ]

        try:
            # We must use create_subprocess_exec to stream IO directly
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(repo_root),
                env={**os.environ, "PYTHONPATH": str(repo_root)},
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,  # Merge stderr into stdout
            )
            self._processes[str_run_id] = proc

            # Start background task to consume stdout
            asyncio.create_task(self._consume_output(str_run_id, proc, run_id))

        except Exception as e:
            logger.error(f"Failed to spawn runner for {run_id}: {e}")
            await self._append_log(pool, run_id, f"CRITICAL RUNNER ERROR: {e}\n")
            await pool.execute(
                "UPDATE hub_runs SET status = 'failed', updated_at = now() WHERE id = $1",
                run_id
            )
            self._completion_events[str_run_id].set()
            self._cleanup_workspace(str_run_id)

    async def _consume_output(self, str_run_id: str, proc: asyncio.subprocess.Process, run_id: UUID):
        """Consume stdout from the subprocess continuously until it exits."""
        pool = get_pool()
        final_status = "failed"
        try:
            if proc.stdout:
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    decoded_line = line.decode('utf-8', errors='replace')
                    await self._append_log(pool, run_id, decoded_line)

            await proc.wait()

            was_cancelled = str_run_id in self._cancelled_runs
            if was_cancelled:
                final_status = "cancelled"
                await self._append_log(pool, run_id, "\nRun finished after cancellation.\n")
            else:
                final_status = "completed" if proc.returncode == 0 else "failed"
                await self._append_log(pool, run_id, f"\nRun finished with exit code {proc.returncode} ({final_status}).\n")

            if proc.returncode == 0 and not was_cancelled:
                success, message = await self._finalize_git_changes(str_run_id, run_id)
                await self._append_log(pool, run_id, f"{message}\n")
                final_status = "completed" if success else "failed"

        except Exception as e:
            logger.error(f"Error reading stdout from run {str_run_id}: {e}")
            await self._append_log(pool, run_id, f"\nFatal error reading logs: {e}\n")

        finally:
            # Cleanup process tracking and finalize DB
            self._processes.pop(str_run_id, None)
            try:
                pool = get_pool()
                await pool.execute(
                    "UPDATE hub_runs SET status = $1, updated_at = now() WHERE id = $2",
                    final_status, run_id
                )
            except Exception as e:
                logger.error(f"Failed to update hub_runs status to {final_status} for {run_id}: {e}")
            self._completion_events[str_run_id].set()
            log_event = self._log_events.get(str_run_id)
            if log_event:
                log_event.set()
            if final_status != "completed":
                self._cleanup_workspace(str_run_id)

    async def _append_log(self, pool, run_id: UUID, line: str):
        try:
            await pool.execute("UPDATE hub_runs SET logs = COALESCE(logs, '') || $1 WHERE id = $2", line, run_id)
            log_event = self._log_events.get(str(run_id))
            if log_event:
                log_event.set()
        except Exception as e:
            logger.error(f"Failed to append log for run {run_id}: {e}")

    async def cancel_run(self, run_id: UUID) -> bool:
        """Terminate an active run."""
        str_run_id = str(run_id)
        proc = self._processes.get(str_run_id)
        pool = get_pool()

        if not proc:
            return False

        # Terminate gently then aggressively if necessary
        try:
            self._cancelled_runs.add(str_run_id)
            proc.terminate()
            await self._append_log(pool, run_id, "\n[RUN CANCELLED BY USER]\n")

            # Update DB eagerly
            pool = get_pool()
            await pool.execute(
                "UPDATE hub_runs SET status = 'cancelled', updated_at = now() WHERE id = $1",
                run_id
            )
            return True
        except ProcessLookupError:
            return False
        except Exception as e:
            logger.error(f"Failed to cancel process {str_run_id}: {e}")
            return False

    async def get_log_iterator(self, run_id: str):
        """
        Yields accumulated logs immediately, then waits for new lines.
        Compatible with FastAPI StreamingResponse for EventSource (SSE).
        """
        pool = get_pool()
        uid_run_id = UUID(run_id)

        # 1. Flush the current buffer
        current_logs = await pool.fetchval("SELECT logs FROM hub_runs WHERE id = $1", uid_run_id)
        if current_logs:
            for line in current_logs.split('\n'):
                if line:
                    yield f"data: {line}\n\n"

        # 2. Wait for process completion or new lines
        # In a robust implementation, this would use asyncio.Queue or Condition
        # instead of polling, but for P1-09 this lightweight async spin works.
        last_len = len(current_logs) if current_logs else 0
        completion_event = self._completion_events.get(run_id)
        log_event = self._log_events.get(run_id)

        while completion_event and not completion_event.is_set():
            if log_event:
                try:
                    await asyncio.wait_for(log_event.wait(), timeout=0.2)
                except asyncio.TimeoutError:
                    pass
                log_event.clear()
            else:
                await asyncio.sleep(0.2)

            current_logs = await pool.fetchval("SELECT logs FROM hub_runs WHERE id = $1", uid_run_id)
            current_len = len(current_logs) if current_logs else 0
            if current_len > last_len:
                new_logs = current_logs[last_len:]
                for line in new_logs.split('\n'):
                    if line:
                        yield f"data: {line}\n\n"
                last_len = current_len

        # Yield any final lines that arrived between loop evaluation and process exit
        current_logs = await pool.fetchval("SELECT logs FROM hub_runs WHERE id = $1", uid_run_id)
        current_len = len(current_logs) if current_logs else 0
        if current_len > last_len:
            new_logs = current_logs[last_len:]
            for line in new_logs.split('\n'):
                if line:
                    yield f"data: {line}\n\n"

        final_status = await pool.fetchval("SELECT status FROM hub_runs WHERE id = $1", uid_run_id)
        yield f"event: status\ndata: {json.dumps({'status': final_status or 'unknown'})}\n\n"
        yield "data: [DONE]\n\n"

# Singleton export
runner = RunManager()
