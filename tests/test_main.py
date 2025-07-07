"""
Tests for __main__.py module.
"""

import os
import sys
from unittest.mock import patch, MagicMock


class TestMainFunction:
    """Test cases for main function."""

    def setup_method(self):
        """Set up test environment."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.__main__ import main

        self.main = main

    def test_main_module_execution(self):
        """Test that main module can be executed."""
        with patch("src.project_manager.main") as mock_main:
            # Import and execute the module
            import src.__main__

            # Check that main was called when __name__ == "__main__"
            # Since we're not running as main, it shouldn't be called
            mock_main.assert_not_called()

    def test_main_module_direct_call(self):
        """Test direct call to main function."""
        with patch("src.project_manager.main") as mock_project_main:
            # Mock the argument parser to avoid SystemExit
            with patch(
                "src.project_manager.argparse.ArgumentParser"
            ) as mock_parser_class:
                mock_parser = MagicMock()
                mock_parser_class.return_value = mock_parser
                mock_parser.parse_args.return_value = MagicMock(
                    operate="build", name="test", args=[], perf_analyze=False
                )

                # Mock ProjectManager to avoid initialization issues
                with patch("src.project_manager.ProjectManager") as mock_pm_class:
                    mock_pm_instance = MagicMock()
                    mock_pm_class.return_value = mock_pm_instance
                    mock_pm_instance.builtin_operations = {"test_op": {"desc": "test"}}

                    self.main()
                    # The main function should not call project_manager.main directly
                    # It should handle the arguments itself
                    mock_project_main.assert_not_called()
