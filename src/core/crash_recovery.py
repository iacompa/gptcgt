"""
Crash recovery and state preservation.
Ensures we don't lose tasks or tokens if the UI crashes.
"""

from __future__ import annotations

import json
import os
import signal
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.core.logger import get_logger

logger = get_logger("core.recovery")


@dataclass
class RecoverableState:
    """Strongly typed representation of application state to preserve."""

    active_task: Optional[str] = None
    progress: int = 0
    pending_diffs: list[str] = None
    _timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecoverableState":
        return cls(**data)


class CrashRecoveryManager:
    """Manages running.lock and state.json for crash detection and recovery."""

    def __init__(self, project_path: Path):
        self.project_path = Path(project_path)
        self.recovery_dir = self.project_path / ".gptcgt" / "recovery"
        self.lock_file = self.recovery_dir / "running.lock"
        self.state_file = self.recovery_dir / "state.json"

        # Ensure directory exists safely
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.recovery_dir, 0o700)
        except Exception:
            pass

    def check_for_crash(self) -> bool:
        """
        Returns True if a previous session crashed (lock file exists and process is dead).
        Also checks for concurrent instances using the PID inside the lock file.
        Raises RuntimeError if a concurrent instance is running.
        """
        if self.lock_file.exists():
            # Check for concurrent instances via PID
            try:
                content = self.lock_file.read_text().strip()
                if content.isdigit():
                    pid = int(content)
                    if pid != os.getpid():
                        try:
                            # Send signal 0 to check if process is alive
                            os.kill(pid, 0)
                            # If we get here, process is alive
                            raise RuntimeError(
                                f"Another instance of gptcgt is already running in this project (PID {pid})."  # noqa: E501
                            )
                        except ProcessLookupError:
                            # Process is dead, lock is stale -> crash detected
                            pass
            except IOError:
                pass
            # Check if there's actual state to recover
            if self.state_file.exists():
                try:
                    with open(self.state_file, "r") as f:
                        data = json.load(f)
                        if data.get("active_task") or data.get("pending_diffs"):
                            logger.warning("Crash detected: running.lock found with active state.")
                            return True
                except Exception as e:
                    logger.error(f"Failed to read recovery state: {e}")

            # Lock exists but no active state to recover -> dirty exit but nothing lost
            logger.info("Found stale lock file but no recoverable state. Cleaning up.")
            self.clear_state()
            return False

        return False

    def get_recovered_state(self) -> Optional[RecoverableState]:
        """Read the saved state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    return RecoverableState.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to parse recovery state: {e}")
        return None

    def save_state(self, state: RecoverableState) -> None:
        """Auto-save current application state."""
        try:
            state._timestamp = datetime.now().isoformat()
            data = state.to_dict()

            # Write to a temp file first, then rename for atomic save
            temp_file = self.state_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_file, self.state_file)
            logger.debug("State auto-saved to disk.")

            # Ensure lock file exists with valid PID
            if not self.lock_file.exists():
                self.acquire_lock()
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def acquire_lock(self) -> None:
        """Create the running.lock file with current PID and bind signals."""
        try:
            pid = os.getpid()
            self.lock_file.write_text(str(pid))
            logger.debug(f"Acquired running.lock with PID {pid}")

            # Register signal handlers for clean exit on kill
            def handle_signal(sig, _frame):
                logger.warning(f"Received signal {sig}, initiating clean shutdown")
                self.clear_state()
                sys.exit(0)

            signal.signal(signal.SIGTERM, handle_signal)
            signal.signal(signal.SIGINT, handle_signal)

        except Exception as e:
            logger.error(f"Failed to create lock file: {e}")

    def clear_state(self) -> None:
        """Cleanly exit: remove lock and state files."""
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
            if self.state_file.exists():
                self.state_file.unlink()
            logger.debug("Cleared recovery state and lock.")
        except Exception as e:
            logger.error(f"Failed to clear recovery state: {e}")


class PendingDiffProtector:
    """Backup utility specifically for unsaved unified diffs that haven't been applied yet."""

    def __init__(self, project_path: Path):
        self.project_path = Path(project_path)
        self.diff_dir = self.project_path / ".gptcgt" / "recovery" / "diffs"
        self.diff_dir.mkdir(parents=True, exist_ok=True)

    def backup_diff(self, file_path: Path, diff_text: str) -> None:
        """Save an unapplied diff to disk."""
        safe_name = str(file_path).replace(os.sep, "_").replace("/", "_") + ".diff"
        backup_path = self.diff_dir / safe_name
        try:
            backup_path.write_text(diff_text, encoding="utf-8")
            logger.debug(f"Backed up pending diff for {file_path.name}")
        except Exception as e:
            logger.error(f"Failed to backup diff: {e}")

    def get_pending_diffs(self) -> dict[str, str]:
        """Return all backed-up diffs."""
        diffs = {}
        if not self.diff_dir.exists():
            return diffs

        for diff_file in self.diff_dir.glob("*.diff"):
            try:
                # We can't easily revert the safe_name back to the absolute path reliably
                # just from the filename if it has underscores, but we can store it in the state.json  # noqa: E501
                # For simplicity, returning the raw text. The coordinator should use state.json
                # to map back to the real file.
                diffs[diff_file.name] = diff_file.read_text(encoding="utf-8")
            except Exception:
                pass
        return diffs

    def clear_diff(self, file_path: Path) -> None:
        """Remove a backup once applied or rejected."""
        safe_name = str(file_path).replace(os.sep, "_").replace("/", "_") + ".diff"
        backup_path = self.diff_dir / safe_name
        if backup_path.exists():
            try:
                backup_path.unlink()
                logger.debug(f"Cleared pending diff backup for {file_path.name}")
            except Exception:
                pass

    def clear_all(self) -> None:
        """Clear all pending diffs (e.g., on fresh start)."""
        if self.diff_dir.exists():
            for f in self.diff_dir.glob("*.diff"):
                try:
                    f.unlink()
                except Exception:
                    pass
