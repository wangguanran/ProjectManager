"""
Log manager module.
"""

import logging
import logging.config
import os

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
                    "()": ColoredFormatter,
                    "format": "[%(asctime)s] [%(levelname)-8s] [%(filename)-24s] [%(funcName)-24s] [%(lineno)-4d] %(message)s",
                },
                "file_formatter": {
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
            print(f"Warning: Failed to create log symlink: {e}")

    def get_logger(self):
        """Get logger instance."""
        return self.logger


log = LogManager().get_logger()
