"""
Tests for log_manager module.
"""

# pylint: disable=attribute-defined-outside-init
# pylint: disable=import-outside-toplevel
# pylint: disable=protected-access

import os
import sys
import tempfile
import logging
from unittest.mock import patch, MagicMock


class TestColoredFormatter:
    """Test cases for ColoredFormatter class."""

    def setup_method(self):
        """Set up test environment for ColoredFormatter tests."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.log_manager import (
            ColoredFormatter,
        )

        self.colored_formatter = ColoredFormatter

    def test_colored_formatter_format(self):
        """Test the format method of ColoredFormatter."""
        formatter = self.colored_formatter()

        record = MagicMock()
        record.levelname = "INFO"
        record.asctime = "2023-01-01 12:00:00"
        record.filename = "test.py"
        record.funcName = "test_function"
        record.lineno = 42
        record.getMessage.return_value = "Test message"
        record.exc_text = None  # Set exc_text to None to avoid mock issues
        record.exc_info = None
        record.stack_info = None
        record.threadName = "MainThread"
        record.processName = "MainProcess"
        record.module = "test"
        record.pathname = "/test/path/test.py"
        record.process = 12345
        record.thread = 67890
        record.msecs = 123
        record.relativeCreated = 123456.789
        record.created = 1640995200.123
        record.name = "test_logger"
        record.msg = "Test message"
        record.args = ()

        result = formatter.format(record)

        # Check that color codes are present
        assert "\033[32m" in result  # Green color for INFO
        assert "\033[0m" in result  # Reset color

        # Check that the message is included
        assert "Test message" in result

    def test_colored_formatter_unknown_level(self):
        """Test ColoredFormatter with unknown log level."""
        formatter = self.colored_formatter()

        record = MagicMock()
        record.levelname = "UNKNOWN"
        record.asctime = "2023-01-01 12:00:00"
        record.filename = "test.py"
        record.funcName = "test_function"
        record.lineno = 42
        record.getMessage.return_value = "Test message"
        record.exc_text = None  # Set exc_text to None to avoid mock issues
        record.exc_info = None
        record.stack_info = None
        record.threadName = "MainThread"
        record.processName = "MainProcess"
        record.module = "test"
        record.pathname = "/test/path/test.py"
        record.process = 12345
        record.thread = 67890
        record.msecs = 123
        record.relativeCreated = 123456.789
        record.created = 1640995200.123
        record.name = "test_logger"
        record.msg = "Test message"
        record.args = ()

        result = formatter.format(record)

        # Should not have color codes for unknown level (no color, but still has reset)
        assert "\033[32m" not in result  # No green color
        assert "\033[36m" not in result  # No cyan color
        assert "\033[33m" not in result  # No yellow color
        assert "\033[31m" not in result  # No red color
        assert "\033[41m" not in result  # No red background
        assert "\033[0m" in result  # Still has reset color
        assert "Test message" in result

    def test_colored_formatter_all_levels(self):
        """Test ColoredFormatter with all log levels."""
        formatter = self.colored_formatter()

        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        colors = ["\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[41m"]

        for level, expected_color in zip(levels, colors):
            record = MagicMock()
            record.levelname = level
            record.asctime = "2023-01-01 12:00:00"
            record.filename = "test.py"
            record.funcName = "test_function"
            record.lineno = 42
            record.getMessage.return_value = f"{level} message"
            record.exc_text = None  # Set exc_text to None to avoid mock issues
            record.exc_info = None
            record.stack_info = None
            record.threadName = "MainThread"
            record.processName = "MainProcess"
            record.module = "test"
            record.pathname = "/test/path/test.py"
            record.process = 12345
            record.thread = 67890
            record.msecs = 123
            record.relativeCreated = 123456.789
            record.created = 1640995200.123
            record.name = "test_logger"
            record.msg = f"{level} message"
            record.args = ()

            result = formatter.format(record)

            assert expected_color in result
            assert "\033[0m" in result
            assert f"{level} message" in result


class TestLogManager:
    """Test cases for LogManager class."""

    def setup_method(self):
        """Set up test environment for LogManager tests."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.log_manager import (
            LogManager,
        )

        self.log_manager = LogManager

    def teardown_method(self):
        """Clean up test environment."""
        # Reset singleton instance
        self.log_manager._LogManager__instance = None

    def test_singleton_pattern(self):
        """Test singleton pattern of LogManager."""
        lm1 = self.log_manager()
        lm2 = self.log_manager()
        assert lm1 is lm2

    def test_logger_initialization(self):
        """Test logger initialization in LogManager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.log_manager.LOG_PATH", os.path.join(temp_dir, "logs")):
                lm = self.log_manager()
                logger = lm.get_logger()

                assert isinstance(logger, logging.Logger)
                assert logger.name == "FileLogger"

    def test_logger_handlers(self):
        """Test logger handlers in LogManager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.log_manager.LOG_PATH", os.path.join(temp_dir, "logs")):
                lm = self.log_manager()
                logger = lm.get_logger()

                # Should have handlers
                assert len(logger.handlers) > 0

    def test_logger_level(self):
        """Test logger level in LogManager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.log_manager.LOG_PATH", os.path.join(temp_dir, "logs")):
                lm = self.log_manager()
                logger = lm.get_logger()

                # Should be DEBUG level
                assert logger.level == logging.DEBUG

    def test_logger_logging(self):
        """Test logger logging in LogManager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.log_manager.LOG_PATH", os.path.join(temp_dir, "logs")):
                lm = self.log_manager()
                logger = lm.get_logger()

                # Test different log levels
                logger.debug("Debug message")
                logger.info("Info message")
                logger.warning("Warning message")
                logger.error("Error message")
                logger.critical("Critical message")

                # Should not raise any exceptions
                assert True

    def test_logger_with_file_handler(self):
        """Test logger with file handler in LogManager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.log_manager.LOG_PATH", os.path.join(temp_dir, "logs")):
                lm = self.log_manager()
                logger = lm.get_logger()

                # Log a message
                test_message = "Test log message"
                logger.info(test_message)

                # Check if log file was created in the logs directory
                logs_dir = os.path.join(temp_dir, "logs")
                if os.path.exists(logs_dir):
                    log_files = [f for f in os.listdir(logs_dir) if f.endswith(".log")]
                    assert len(log_files) > 0
                else:
                    # If logs directory doesn't exist, check if any .log files were created in temp_dir
                    log_files = [f for f in os.listdir(temp_dir) if f.endswith(".log")]
                    assert len(log_files) > 0

    def test_logger_multiple_instances(self):
        """Test multiple instances of LogManager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.log_manager.LOG_PATH", os.path.join(temp_dir, "logs")):
                lm1 = self.log_manager()
                lm2 = self.log_manager()

                logger1 = lm1.get_logger()
                logger2 = lm2.get_logger()

                # Should be the same logger instance
                assert logger1 is logger2


class TestLogManagerIntegration:
    """Integration tests for LogManager."""

    def setup_method(self):
        """Set up test environment for LogManager integration tests."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.log_manager import (
            LogManager,
        )

        self.log_manager = LogManager

    def test_logger_with_real_file_output(self):
        """Test logger with real file output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.log_manager.LOG_PATH", os.path.join(temp_dir, "logs")):
                lm = self.log_manager()
                logger = lm.get_logger()

                # Log messages
                logger.info("Integration test message")
                logger.warning("Integration test warning")

                # Check log directory was created
                assert os.path.exists(os.path.join(temp_dir, "logs"))

    def test_logger_with_organize_files(self):
        """Test logger with organize files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.log_manager.LOG_PATH", os.path.join(temp_dir, "logs")):
                # Create some existing log files
                os.makedirs(os.path.join(temp_dir, "logs"), exist_ok=True)
                existing_log = os.path.join(temp_dir, "logs", "log_old.txt")
                with open(existing_log, "w", encoding="utf-8") as f:
                    f.write("Old log content")

                # Initialize LogManager (should organize files)
                lm = self.log_manager()
                logger = lm.get_logger()

                # Log a new message
                logger.info("New log message")

                # Should not raise exceptions
                assert True


class TestGlobalLog:
    """Test cases for global log instance."""

    def setup_method(self):
        """Set up test environment for global log tests."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.log_manager import log

        self.log = log

    def test_global_log_instance(self):
        """Test global log instance."""
        assert self.log is not None
        assert isinstance(self.log, logging.Logger)

    def test_global_log_functionality(self):
        """Test global log functionality."""
        # Should be able to log messages without exceptions
        self.log.debug("Global debug message")
        self.log.info("Global info message")
        self.log.warning("Global warning message")
        self.log.error("Global error message")
        self.log.critical("Global critical message")

        assert True

    def test_global_log_levels(self):
        """Test global log levels."""
        # Test that we can check log levels
        assert self.log.isEnabledFor(logging.DEBUG)
        assert self.log.isEnabledFor(logging.INFO)
        assert self.log.isEnabledFor(logging.WARNING)
        assert self.log.isEnabledFor(logging.ERROR)
        assert self.log.isEnabledFor(logging.CRITICAL)

    def test_global_log_handlers(self):
        """Test global log handlers."""
        # Should have handlers configured
        assert len(self.log.handlers) > 0

        # Check handler types
        handler_types = [type(handler) for handler in self.log.handlers]
        assert (
            logging.StreamHandler in handler_types
            or logging.FileHandler in handler_types
        )
