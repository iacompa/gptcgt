from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from src.core.workspace import Workspace


class MessageRole(Enum):
    USER = "user"
    AGENT = "agent"
    ORCHESTRATOR = "orchestrator"
    ARBITER = "arbiter"
    SYSTEM = "system"


Role = MessageRole  # Alias for ChatPipeline


@dataclass
class ChatMessage:
    id: str  # UUID4
    role: MessageRole
    content: str  # Full text (markdown supported)
    timestamp: datetime
    agent_id: str | None = None  # Which model responded (e.g. "claude-sonnet")
    agent_color: str | None = None  # Hex color for display (e.g. "#A78BFA")
    task_id: str | None = None  # Groups messages belonging to same task
    files_referenced: list[str] = field(default_factory=list)
    cost: float | None = None  # Cost of this specific response
    tokens_used: int = 0  # Tokens consumed for this message exchange
    mode: str | None = None  # "scout", "standard", "ensemble", etc.
    metadata: dict = field(default_factory=dict)  # Extensible for arbiter verdicts, diffs, etc.

    def to_dict(self) -> dict:
        d = asdict(self)
        d["role"] = self.role.value
        d["timestamp"] = self.timestamp.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        d = dict(data)
        d["role"] = MessageRole(d["role"])
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        # Filter to known fields for forward compatibility
        import dataclasses
        known_fields = {f.name for f in dataclasses.fields(cls)}
        d = {k: v for k, v in d.items() if k in known_fields}
        return cls(**d)


class ChatStore:
    def __init__(self, workspace: Workspace) -> None:
        """Initialize with workspace for safe file access."""
        self.workspace = workspace
        self.sessions_dir = self.workspace.get_project_root() / ".gptcgt" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.current_session_id: str | None = None
        self._cache: list[ChatMessage] = []

    def new_session(self) -> str:
        """Start a new session. Returns session_id (timestamp-based)."""
        session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.current_session_id = session_id
        self._cache = []

        session_file = self._get_session_path(session_id)
        if not session_file.exists():
            self._save_to_disk(session_file, [])

        self._update_current_symlink(session_file)
        return session_id

    def add_message(
        self,
        role: MessageRole,
        content: str,
        model_id: str | None = None,
        tokens_used: int = 0,
        **kwargs,
    ) -> ChatMessage:
        """Append a message to the current session and return it. Auto-saves to disk."""
        if not self.current_session_id:
            self.new_session()

        msg = ChatMessage(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            timestamp=datetime.now(),
            agent_id=model_id,
            tokens_used=tokens_used,
            **kwargs,
        )

        self._cache.append(msg)
        session_file = self._get_session_path(self.current_session_id)  # type: ignore
        self._save_to_disk(session_file, self._cache)
        return msg

    def truncate_history(self, keep_count: int, summary_msg: ChatMessage) -> None:
        """Truncates the session history keeping the last `keep_count` messages, and prepends the summary."""
        if not self.current_session_id:
            return
  # noqa: W293
        if len(self._cache) <= keep_count:
            return
  # noqa: W293
        recent = self._cache[-keep_count:]
        self._cache = [summary_msg] + recent
  # noqa: W293
        session_file = self._get_session_path(self.current_session_id)
        self._save_to_disk(session_file, self._cache)

    def get_session_messages(self, session_id: str | None = None) -> list[ChatMessage]:
        """Get all messages for a session. None = current session."""
        target_id = session_id or self.current_session_id
        if not target_id:
            return []

        if target_id == self.current_session_id and self._cache:
            return list(self._cache)

        session_file = self._get_session_path(target_id)
        if not session_file.exists():
            return []

        return self._load_from_disk(session_file)

    def get_recent_messages(self, count: int = 50) -> list[ChatMessage]:
        """Get the N most recent messages from current session."""
        msgs = self.get_session_messages()
        return msgs[-count:] if len(msgs) > count else msgs

    def list_sessions(self) -> list[dict]:
        """List all saved sessions with date, message count, and first message preview."""
        sessions = []
        for file_path in self.sessions_dir.glob("*.json"):
            if file_path.name == "current.json":
                continue
            messages = self._load_from_disk(file_path)
            preview = ""
            for msg in messages:
                if msg.role == MessageRole.USER:
                    preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                    break

            sessions.append(
                {
                    "id": file_path.stem,
                    "date": file_path.stat().st_mtime,
                    "message_count": len(messages),
                    "preview": preview,
                }
            )

        sessions.sort(key=lambda x: x["date"], reverse=True)
        return sessions

    def search_sessions(self, query: str) -> list[tuple[str, ChatMessage]]:
        """Full-text search across all sessions. Returns (session_id, matching message)."""
        results = []
        query_lower = query.lower()
        for file_path in self.sessions_dir.glob("*.json"):
            if file_path.name == "current.json":
                continue
            session_id = file_path.stem
            messages = self._load_from_disk(file_path)
            for msg in messages:
                if query_lower in msg.content.lower():
                    results.append((session_id, msg))
        return results

    def delete_session(self, session_id: str) -> None:
        """Delete a specific session from disk."""
        session_file = self._get_session_path(session_id)
        if session_file.exists():
            session_file.unlink()

        if self.current_session_id == session_id:
            self.current_session_id = None
            self._cache = []

    def export_session(self, session_id: str, format: str = "markdown") -> str:
        """Export a session as readable markdown."""
        messages = self.get_session_messages(session_id)
        lines = [f"# Chat Session: {session_id}\n"]
        for msg in messages:
            lines.append(f"**{msg.role.value.upper()}** ({msg.timestamp.strftime('%H:%M:%S')})")
            if msg.agent_id:
                lines.append(f"*{msg.agent_id}*")
            lines.append(f"\n{msg.content}\n")
            lines.append("---\n")
        return "\n".join(lines)

    def load_active_session(self) -> None:
        """Load the most recent session or start a new one."""
        sessions = self.list_sessions()
        if sessions:
            latest_id = sessions[0]["id"]
            self.current_session_id = latest_id
            self._cache = self._load_from_disk(self._get_session_path(latest_id))
            self._update_current_symlink(self._get_session_path(latest_id))
        else:
            self.new_session()

    def _get_session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def _save_to_disk(self, file_path: Path, messages: list[ChatMessage]) -> None:
        """Atomic write to disk."""
        temp_path = file_path.with_suffix(".json.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump([m.to_dict() for m in messages], f, indent=2)
            temp_path.replace(file_path)  # Atomic replace
        except Exception:
            if temp_path.exists():
                temp_path.unlink()

    def _load_from_disk(self, file_path: Path) -> list[ChatMessage]:
        if not file_path.exists():
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [ChatMessage.from_dict(d) for d in data]
        except (json.JSONDecodeError, KeyError):
            return []

    def _update_current_symlink(self, target: Path) -> None:
        current_link = self.sessions_dir / "current.json"
        try:
            if current_link.exists() or current_link.is_symlink():
                current_link.unlink()
            # Some OS restrict symlinks, fallback to copy if needed
            try:
                current_link.symlink_to(target.name)
            except OSError:
                shutil.copy2(target, current_link)
        except Exception:
            pass  # Non-critical if current.json link fails
