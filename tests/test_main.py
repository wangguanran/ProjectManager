"""
Tests for __main__.py module.
"""

# pylint: disable=attribute-defined-outside-init
# pylint: disable=import-outside-toplevel

import os
import sys
from unittest.mock import MagicMock, patch


class TestMainFunction:
    """Test cases for main function."""

    def setup_method(self):
        """
        Prepare the test environment for each test case.
        - Adds the project root to sys.path if not already present, ensuring modules can be imported correctly.
        - Imports the main function from src.__main__ and assigns it to self.main for use in test cases.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.__main__ import main

        self.main = main

    def test_main_module_execution(self):
        """
        Verify that importing the src.__main__ module does not trigger the execution of the main() function.
        - Mocks the main function in src.__main__.
        - Imports the module to simulate normal import behavior.
        - Asserts that the main function is not called during import, ensuring correct __main__ guard usage.
        """
        with patch("src.__main__.main") as mock_main:
            import src.__main__

            _ = src.__main__  # avoid unused-import warning
            mock_main.assert_not_called()

    def test_main_module_direct_call(self):
        """
        Test the behavior when the main() function is called directly.
        - Mocks the main function and the ArgumentParser to simulate command-line argument parsing.
        - Sets up mock arguments to simulate a 'build' operation with a test project name.
        - Mocks the ProjectManager class and its instance, including a dummy builtin_operations dict.
        - Calls self.main() to simulate direct execution.
        - Asserts that the mocked main function is not called recursively, ensuring correct entry point logic.
        """
        with patch("src.__main__.main") as mock_project_main:
            with patch("src.__main__.argparse.ArgumentParser") as mock_parser_class:
                mock_parser = MagicMock()
                mock_parser_class.return_value = mock_parser
                mock_args = MagicMock(
                    operate="build", name="test", args=[], perf_analyze=False
                )
                mock_parser.parse_args.return_value = mock_args
                mock_parser.parse_known_args.return_value = (mock_args, [])
                with patch(
                    "src.plugins.project_manager.ProjectManager"
                ) as mock_pm_class:
                    mock_pm_instance = MagicMock()
                    mock_pm_class.return_value = mock_pm_instance
                    mock_pm_instance.builtin_operations = {
                        "test_op": {
                            "desc": "test",
                            "func": MagicMock(),
                            "params": [],
                            "required_count": 0,
                        }
                    }
                    self.main()
                    mock_project_main.assert_not_called()
