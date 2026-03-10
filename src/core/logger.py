"""
Structured logging for gptcgt.

Every component gets a named logger. Logs go to three destinations:
1. File: .gptcgt/logs/gptcgt.log (always, all levels)
2. Debug file: .gptcgt/logs/debug.log (DEBUG and above, rotated daily)
3. TUI: LogPanel widget for real-time viewing (INFO and above)

Log format is structured for easy parsing:
2026-02-21 14:30:02.123 | INFO     | orchestrator | Dispatching Claude for task "fix auth bug"
"""

from __future__ import annotations

import logging
import os
import re
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Callable


class GptcgtFormatter(logging.Formatter):
    """
    Custom formatter producing structured, parseable log lines.

    Format: TIMESTAMP | LEVEL | COMPONENT | MESSAGE

    For JSON-structured data (API calls, costs, events), append as key=value pairs.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record."""
        timestamp = datetime.fromtimestamp(record.created).isoformat(timespec="milliseconds")
        level_name = f"{record.levelname:8}"
        component = f"{record.name:15}"
        message = record.getMessage()

        base_log = f"{timestamp} | {level_name} | {component} | {message}"

        # If record has extra 'structured_data' dict, append as key=value pairs
        if hasattr(record, "structured_data") and isinstance(record.structured_data, dict):
            extra_pairs = []
            for k, v in record.structured_data.items():
                extra_pairs.append(f"{k}={v}")
            if extra_pairs:
                base_log += " | " + " ".join(extra_pairs)

        # Handle exception information if present
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)

        if record.exc_text:
            base_log += "\n" + record.exc_text

        # Final string-level redaction catch-all (catches leaks in tracebacks)
        for pattern, replacement in SensitiveDataFilter.PATTERNS:
            base_log = pattern.sub(replacement, base_log)

        return base_log


class SensitiveDataFilter(logging.Filter):
    """
    CRITICAL SECURITY FILTER.

    Scrubs sensitive data from ALL log output.
    This filter is applied to EVERY handler. No exceptions.
    """

    # Patterns to match and redact
    PATTERNS = [
        # Match sk-... (OpenAI or Anthropic style keys). Keeps 'sk-...' plus 8 chars, then dots, then last 4 chars.  # noqa: E501
        (
            re.compile(r"(sk-(?:ant-api03-|proj-|svc-)?[a-zA-Z0-9]{8})[a-zA-Z0-9_\-]+([a-zA-Z0-9]{4})"),
            r"\1...\2",
        ),
        # Bearer tokens
        (re.compile(r"(Bearer\s+)[a-zA-Z0-9._\-]{8,}", re.IGNORECASE), r"\1...XXXX"),
        # api_key / password assignment
        (
            re.compile(
                r'((?:api_key|apikey|password|secret|token|auth)\s*[:=]\s*["\']?)[^\s"\'}]+',
                re.IGNORECASE,
            ),
            r"\1***REDACTED***",
        ),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Scrub the record message and args. Always returns True."""
        msg = str(record.msg)

        # Scrub main message
        for pattern, replacement in self.PATTERNS:
            msg = pattern.sub(replacement, msg)

        record.msg = msg

        # Scrub dictionary arguments if present
        if isinstance(record.args, dict):
            scrubbed_args = {}
            for k, v in record.args.items():
                val_str = str(v)
                for pattern, replacement in self.PATTERNS:
                    val_str = pattern.sub(replacement, val_str)
                scrubbed_args[k] = val_str
            record.args = scrubbed_args
        elif isinstance(record.args, tuple) and len(record.args) > 0:
            scrubbed_args = []
            for v in record.args:
                val_str = str(v)
                for pattern, replacement in self.PATTERNS:
                    val_str = pattern.sub(replacement, val_str)
                scrubbed_args.append(val_str)
            record.args = tuple(scrubbed_args)

        # Scrub structured data if present
        if hasattr(record, "structured_data") and isinstance(record.structured_data, dict):
            for k, v in record.structured_data.items():
                if any(sec in k.lower() for sec in ["api_key", "apikey", "password", "secret", "token", "auth"]):
                    record.structured_data[k] = "***REDACTED***"
                else:
                    val_str = str(v)
                    for pattern, replacement in self.PATTERNS:
                        val_str = pattern.sub(replacement, val_str)
                    record.structured_data[k] = val_str

        return True


class LogBuffer(logging.Handler):
    """
    In-memory ring buffer of recent log entries for the TUI log viewer.

    Stores the last 500 formatted log entries.
    The TUI can subscribe to new entries via a callback.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.buffer = deque(maxlen=500)
            cls._instance.subscribers = []
            # Make sure to initialize the Handler internals
            logging.Handler.__init__(cls._instance, *args, **kwargs)
        return cls._instance

    def __init__(self, level=logging.NOTSET):
        # Prevent re-initialization of handler base state
        pass

    def emit(self, record: logging.LogRecord) -> None:
        """Process a log record and notify subscribers."""
        try:
            formatted_message = self.format(record)
            self.buffer.append(formatted_message)
            for callback in self.subscribers:
                try:
                    callback(formatted_message)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)

    def get_recent(self, n: int = 50) -> list[str]:
        """Get last N entries."""
        return list(self.buffer)[-n:]

    def subscribe(self, callback: Callable[[str], None]) -> None:
        """Called on every new entry."""
        if callback not in self.subscribers:
            self.subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[str], None]) -> None:
        """Remove callback."""
        if callback in self.subscribers:
            self.subscribers.remove(callback)


def setup_logging(project_path: Path, debug: bool = False) -> None:
    """Initialize the logging system. Call once at app startup."""
    global _last_log_dir  # noqa: PLW0603

    # Create logs directory securely
    log_dir = project_path / ".gptcgt" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Try to set owner-only permissions if posix
    if os.name == "posix":
        try:
            log_dir.chmod(0o700)
        except Exception:
            pass

    # Root logger setup
    root_logger = logging.getLogger("gptcgt")

    # Allow re-initialization when project_path changes (tests, workspace switch)
    if root_logger.handlers and getattr(setup_logging, "_last_log_dir", None) == str(log_dir):
        return
    # Remove stale file handlers from a previous project_path
    for h in list(root_logger.handlers):
        if isinstance(h, (RotatingFileHandler, TimedRotatingFileHandler)):
            h.close()
            root_logger.removeHandler(h)
    setup_logging._last_log_dir = str(log_dir)

    final_debug = debug or os.environ.get("GPTCGT_DEBUG", "").lower() in ["1", "true", "yes"]
    root_logger.setLevel(logging.DEBUG if final_debug else logging.INFO)

    # Formatter and Filter
    formatter = GptcgtFormatter()
    sensitive_filter = SensitiveDataFilter()

    # 1. Main Log Handler (Rotating, max 5MB, keep 3 backups)
    main_log_file = log_dir / "gptcgt.log"
    main_handler = RotatingFileHandler(main_log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
    main_handler.setLevel(logging.DEBUG if final_debug else logging.INFO)
    main_handler.setFormatter(formatter)
    main_handler.addFilter(sensitive_filter)
    root_logger.addHandler(main_handler)

    # 2. Debug Log Handler (Time rotated daily, keep 7 days)
    debug_log_file = log_dir / "debug.log"
    debug_handler = TimedRotatingFileHandler(debug_log_file, when="midnight", interval=1, backupCount=7)
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(formatter)
    debug_handler.addFilter(sensitive_filter)
    root_logger.addHandler(debug_handler)

    # 3. TUI In-Memory Handler
    buffer_handler = LogBuffer()
    buffer_handler.setLevel(logging.DEBUG if final_debug else logging.INFO)
    buffer_handler.setFormatter(formatter)
    buffer_handler.addFilter(sensitive_filter)
    root_logger.addHandler(buffer_handler)

    # Also capture warnings
    logging.captureWarnings(True)
    warnings_logger = logging.getLogger("py.warnings")
    for handler in root_logger.handlers:
        warnings_logger.addHandler(handler)


def get_logger(component: str) -> logging.Logger:
    """Get a named logger for a component."""
    return logging.getLogger(f"gptcgt.{component}")
