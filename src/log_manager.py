"""Centralised logging utilities."""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Any, Dict

from src.utils import get_filename, path_from_root

LOG_PATH = Path(path_from_root(".cache", "logs"))
LATEST_LOG_LINK = Path(path_from_root(".cache", "latest.log"))
LOG_FORMAT = (
    "[%(asctime)s] [%(levelname)-8s] [%(filename)-24s] "
    "[%(funcName)-24s] [%(lineno)-4d] %(message)s"
)

# ANSI color codes for log levels
LOG_COLORS = {
    "DEBUG": "\033[36m",  # Cyan
    "INFO": "\033[32m",  # Green
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",  # Red
    "CRITICAL": "\033[41m",  # Red background
}
RESET_COLOR = "\033[0m"


class ColoredFormatter(logging.Formatter):
    """Formatter with ANSI color codes for log levels."""

    def format(self, record):
        levelname = record.levelname
        color = LOG_COLORS.get(levelname, "")
        # Format the whole line first
        formatted = super().format(record)
        # Add color to the whole line
        return f"{color}{formatted}{RESET_COLOR}"


class LogManager:
    """Singleton manager that configures and exposes the application logger."""

    __instance: "LogManager | None" = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
            cls.__instance._logger = None  # type: ignore[attr-defined]
        return cls.__instance

    def __init__(self):
        if getattr(self, "_logger", None) is None:
            self._logger = self._init_logger()

    @staticmethod
    def _init_logger() -> logging.Logger:
        """Initialise and configure the main project logger."""

        log_directory = LOG_PATH
        log_file_path = Path(get_filename("Log_", ".log", log_directory))

        config = LogManager._build_logging_config(log_file_path)
        logging.config.dictConfig(config)

        LogManager._create_latest_log_link(log_file_path)
        return logging.getLogger("FileLogger")

    @staticmethod
    def _build_logging_config(log_file_path: Path) -> Dict[str, Any]:
        """Return the logging configuration dictionary."""

        return {
            "version": 1,
            "formatters": {
                "console_formatter": {
                    "()": ColoredFormatter,
                    "format": LOG_FORMAT,
                },
                "file_formatter": {
                    "format": LOG_FORMAT,
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
                    "filename": str(log_file_path),
                    "level": "DEBUG",
                    "mode": "w",
                    "formatter": "file_formatter",
                    "encoding": "utf8",
                    "delay": True,
                },
                "file_base_time": {
                    "class": "logging.handlers.TimedRotatingFileHandler",
                    "filename": "Log.log",
                    "level": "DEBUG",
                    "formatter": "file_formatter",
                    "encoding": "utf8",
                    "delay": True,
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

    @staticmethod
    def _create_latest_log_link(log_file_path: Path) -> None:
        """Create or refresh the ``latest.log`` symbolic link."""

        try:
            cache_dir = LATEST_LOG_LINK.parent
            cache_dir.mkdir(parents=True, exist_ok=True)

            if LATEST_LOG_LINK.exists() or LATEST_LOG_LINK.is_symlink():
                LATEST_LOG_LINK.unlink()

            LATEST_LOG_LINK.symlink_to(log_file_path)
        except OSError as exc:  # pragma: no cover - platform dependent
            print(f"Warning: Failed to create log symlink: {exc}")

    def get_logger(self) -> logging.Logger:
        """Return the configured logger instance."""

        return self._logger


log = LogManager().get_logger()
