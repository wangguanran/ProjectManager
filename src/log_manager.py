"""
Log manager module.
"""

from __future__ import annotations

import json
import logging
import logging.config
import os
import re
import sys
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from src.execution import ExecutionSession

from src.utils import get_filename

LOG_PATH = os.path.join(os.getcwd(), ".cache", "logs")
LATEST_LOG_LINK = os.path.join(os.getcwd(), ".cache", "latest.log")

# ANSI color codes for log levels
LOG_COLORS = {
    "DEBUG": "\033[36m",  # Cyan
    "INFO": "\033[32m",  # Green
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",  # Red
    "CRITICAL": "\033[41m",  # Red background
}
RESET_COLOR = "\033[0m"

_REDACTION_RULES: list[tuple[re.Pattern[str], str]] = [
    # GitHub tokens
    (re.compile(r"\bghp_[A-Za-z0-9]{36}\b"), "ghp_***"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"), "github_pat_***"),
    # AWS access keys (best-effort)
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AKIA****************"),
    (re.compile(r"\bASIA[0-9A-Z]{16}\b"), "ASIA****************"),
    # Common auth headers / params
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]+"), "Bearer ***"),
    (re.compile(r"(?i)\b(access_token|refresh_token|id_token)\s*[:=]\s*([^\s'\"\\]+)"), r"\1=***"),
    (re.compile(r"(?i)\b(access_token|refresh_token|id_token)=([^&\s]+)"), r"\1=***"),
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*([^\s'\"\\]+)"), r"\1=***"),
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password)=([^&\s]+)"), r"\1=***"),
    # Basic auth in URLs
    (re.compile(r"(https?://)([^/@:\s]+):([^@/\s]+)@"), r"\1\2:***@"),
]


def redact_secrets(text: Any) -> str:
    """Best-effort secret redaction for logs. Keeps output readable."""
    if text is None:
        return ""
    value = str(text)
    for pattern, replacement in _REDACTION_RULES:
        value = pattern.sub(replacement, value)
    return value


def summarize_output(text: Any, *, max_tail_lines: int = 20, max_tail_chars: int = 400) -> str:
    """Summarize potentially-large stdout/stderr for safe logging."""
    if text is None:
        return ""
    value = str(text)
    if not value:
        return ""
    total_len = len(value)
    lines = value.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    tail = "\n".join(lines[-max_tail_lines:])
    if len(tail) > max_tail_chars:
        tail = tail[-max_tail_chars:]
    tail = redact_secrets(tail)
    tail_single = " | ".join(line.strip() for line in tail.splitlines() if line.strip())
    if len(tail_single) > max_tail_chars:
        tail_single = tail_single[-max_tail_chars:]
    return f"[len={total_len} tail={tail_single}]"


class ColoredFormatter(logging.Formatter):
    """Formatter with ANSI color codes for log levels."""

    def format(self, record):
        levelname = record.levelname
        color = LOG_COLORS.get(levelname, "")
        # Format the whole line first
        formatted = super().format(record)
        # Add color to the whole line
        return f"{color}{formatted}{RESET_COLOR}"


class RedactingFormatter(logging.Formatter):
    """Formatter that redacts common secret patterns from the final log line."""

    def format(self, record):
        formatted = super().format(record)
        return redact_secrets(formatted)


class RedactingColoredFormatter(ColoredFormatter):
    """Colored formatter that also redacts common secret patterns."""

    def format(self, record):
        formatted = super().format(record)
        return redact_secrets(formatted)


class LogManager:
    """Log manager singleton class."""

    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self):
        self.logger = self._init_logger()

    @staticmethod
    def _init_logger():
        """Initialize logger."""
        # Generate log file path
        log_file_path = get_filename("Log_", ".log", LOG_PATH)

        config = {
            "version": 1.0,
            "formatters": {
                "console_formatter": {
                    "()": RedactingColoredFormatter,
                    "format": "[%(asctime)s] [%(levelname)-8s] [%(filename)-24s] [%(funcName)-24s] [%(lineno)-4d] %(message)s",
                },
                "file_formatter": {
                    "()": RedactingFormatter,
                    "format": "[%(asctime)s] [%(levelname)-8s] [%(filename)-24s] [%(funcName)-24s] [%(lineno)-4d] %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "INFO",
                    "formatter": "console_formatter",
                },
                "file": {
                    "class": "logging.FileHandler",
                    "filename": log_file_path,
                    "level": "DEBUG",
                    "mode": "w",
                    "formatter": "file_formatter",
                    "encoding": "utf8",
                    "delay": "True",
                },
                "file_base_time": {
                    "class": "logging.handlers.TimedRotatingFileHandler",
                    "filename": "Log.log",
                    "level": "DEBUG",
                    "formatter": "file_formatter",
                    "encoding": "utf8",
                    "delay": "True",
                },
            },
            "loggers": {
                "StreamLogger": {
                    "handlers": ["console"],
                    "level": "DEBUG",
                },
                "FileLogger": {
                    "handlers": ["console", "file"],
                    "level": "DEBUG",
                },
            },
        }
        logging.config.dictConfig(config)

        # Create symbolic link to latest log file
        LogManager._create_latest_log_link(log_file_path)

        return logging.getLogger("FileLogger")

    @staticmethod
    def _create_latest_log_link(log_file_path):
        """Create symbolic link to latest log file."""
        try:
            # Ensure .cache directory exists
            cache_dir = os.path.dirname(LATEST_LOG_LINK)
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)

            # Remove existing link if it exists
            if os.path.exists(LATEST_LOG_LINK) or os.path.islink(LATEST_LOG_LINK):
                os.remove(LATEST_LOG_LINK)

            # Create symbolic link
            os.symlink(log_file_path, LATEST_LOG_LINK)
        except OSError as e:
            # If symlink creation fails, log the error but don't crash
            # IMPORTANT: write to stderr (stdout must stay clean for machine-readable use cases).
            print(f"Warning: Failed to create log symlink: {e}", file=sys.stderr)

    def get_logger(self):
        """Get logger instance."""
        return self.logger


log = LogManager().get_logger()


class ExecutionSessionLogHandler(logging.Handler):
    """Route logger records into the active execution-session step."""

    def __init__(self, session: "ExecutionSession") -> None:
        super().__init__(level=logging.INFO)
        self._session = session
        self.setFormatter(RedactingFormatter("[%(levelname)-8s] %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:  # pragma: no cover - logging handlers must never raise
            self.handleError(record)
            return

        stream = "stderr" if record.levelno >= logging.WARNING else "stdout"
        self._session.log(message, stream=stream)


def attach_execution_session_logging(
    session: "ExecutionSession", *, logger: Optional[logging.Logger] = None
) -> ExecutionSessionLogHandler:
    """Attach a temporary logger handler that forwards records into an execution session."""
    target_logger = logger or log
    handler = ExecutionSessionLogHandler(session)
    target_logger.addHandler(handler)
    return handler


def detach_execution_session_logging(
    handler: Optional[ExecutionSessionLogHandler], *, logger: Optional[logging.Logger] = None
) -> None:
    """Remove a previously-attached execution-session log handler."""
    if handler is None:
        return
    target_logger = logger or log
    target_logger.removeHandler(handler)
    handler.close()


def mute_console_logging() -> list[tuple[logging.Handler, int]]:
    """Temporarily raise console handlers above CRITICAL, preserving file logging."""
    saved: list[tuple[logging.Handler, int]] = []
    for handler in list(log.handlers):
        if isinstance(handler, logging.FileHandler):
            continue
        if isinstance(handler, logging.StreamHandler):
            saved.append((handler, handler.level))
            handler.setLevel(logging.CRITICAL + 1)
    return saved


def restore_console_logging(saved: list[tuple[logging.Handler, int]]) -> None:
    """Restore console handler levels saved by `mute_console_logging()`."""
    for handler, level in saved:
        handler.setLevel(level)


def log_cmd_event(
    logger: logging.Logger,
    *,
    command: Any,
    cwd: Optional[str],
    description: str,
    returncode: int,
    stdout: str,
    stderr: str,
) -> None:
    """Emit a structured command execution event as a single JSON line (debug level)."""
    payload = {
        "type": "cmd",
        "desc": description,
        "cwd": cwd or "",
        "cmd": command,
        "rc": int(returncode),
        "stdout_len": len(stdout or ""),
        "stderr_len": len(stderr or ""),
    }
    logger.debug("CMD_JSON %s", json.dumps(payload, ensure_ascii=False))
