"""
Tests for project_manager module.
"""

import sys
import os
import tempfile
import shutil
import configparser
import pytest
from unittest.mock import patch, MagicMock


class TestProjectManager:
    """Test cases for ProjectManager class."""

    def setup_method(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.project_manager import ProjectManager

        self.project_manager = ProjectManager
        # Reset singleton instance
        self.project_manager._instance = None
        self.project_manager._initialized = False

    def teardown_method(self):
        """Clean up test environment."""
        # Reset singleton instance
        self.project_manager._instance = None
        self.project_manager._initialized = False

    def test_singleton_pattern(self):
        """Test that ProjectManager follows singleton pattern."""
        pm1 = self.project_manager()
        pm2 = self.project_manager()
        assert pm1 is pm2

    def test_initialization_only_once(self):
        """Test that initialization happens only once."""
        pm1 = self.project_manager()
        pm2 = self.project_manager()
        # Both should be the same instance
        assert pm1 is pm2
        # Both should have the same initialized state
        assert pm1._initialized is True
        assert pm2._initialized is True

    @patch("src.project_manager.path_from_root")
    def test_load_all_projects_no_vprojects_dir(self, mock_path_from_root):
        """Test loading projects when vprojects directory doesn't exist."""
        mock_path_from_root.return_value = "/nonexistent/path"
        pm = self.project_manager()
        assert pm.all_projects_info == {}

    @patch("src.project_manager.path_from_root")
    def test_load_all_projects_empty_directory(self, mock_path_from_root):
        """Test loading projects from empty vprojects directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_path_from_root.return_value = temp_dir
            pm = self.project_manager()
            assert pm.all_projects_info == {}

    @patch("src.project_manager.path_from_root")
    def test_load_all_projects_with_valid_ini(self, mock_path_from_root):
        """Test loading projects with valid ini file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create board directory
            board_dir = os.path.join(temp_dir, "test_board")
            os.makedirs(board_dir)

            # Create ini file
            ini_file = os.path.join(board_dir, "test_board.ini")
            config = configparser.ConfigParser()
            config.add_section("test_project")
            config.set("test_project", "PROJECT_PO_CONFIG", "po_test01")
            config.set("test_project", "build_type", "debug")

            with open(ini_file, "w", encoding="utf-8") as f:
                config.write(f)

            mock_path_from_root.return_value = temp_dir
            pm = self.project_manager()

            # Check that project info was loaded correctly
            assert "test_project" in pm.all_projects_info
            assert (
                pm.all_projects_info["test_project"]["PROJECT_PO_CONFIG"] == "po_test01"
            )
            assert pm.all_projects_info["test_project"]["BUILD_TYPE"] == "debug"
            assert pm.all_projects_info["test_project"]["board_name"] == "test_board"

    @patch("src.project_manager.path_from_root")
    def test_load_all_projects_with_duplicate_keys(self, mock_path_from_root):
        """Test loading projects with duplicate keys in ini file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create board directory
            board_dir = os.path.join(temp_dir, "test_board")
            os.makedirs(board_dir)

            # Create ini file with duplicate keys
            ini_file = os.path.join(board_dir, "test_board.ini")
            with open(ini_file, "w", encoding="utf-8") as f:
                f.write("[test_project]\n")
                f.write("PROJECT_PO_CONFIG=po_test01\n")
                f.write("PROJECT_PO_CONFIG=po_test02\n")  # Duplicate key

            mock_path_from_root.return_value = temp_dir
            pm = self.project_manager()

            # Should skip this ini file due to duplicate keys
            assert pm.all_projects_info == {}

    @patch("src.project_manager.path_from_root")
    def test_load_all_projects_with_parent_child_inheritance(self, mock_path_from_root):
        """Test parent-child inheritance in project configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create board directory
            board_dir = os.path.join(temp_dir, "test_board")
            os.makedirs(board_dir)

            # Create ini file with parent and child projects
            ini_file = os.path.join(board_dir, "test_board.ini")
            config = configparser.ConfigParser()

            # Parent project
            config.add_section("parent-project")
            config.set("parent-project", "PROJECT_PO_CONFIG", "po_parent")
            config.set("parent-project", "build_type", "release")

            # Child project
            config.add_section("parent-project-child")
            config.set("parent-project-child", "PROJECT_PO_CONFIG", "po_child")
            config.set("parent-project-child", "DEBUG_LEVEL", "high")

            with open(ini_file, "w", encoding="utf-8") as f:
                config.write(f)

            mock_path_from_root.return_value = temp_dir
            pm = self.project_manager()

            # Check parent project
            assert "parent-project" in pm.all_projects_info
            assert (
                pm.all_projects_info["parent-project"]["PROJECT_PO_CONFIG"]
                == "po_parent"
            )
            assert pm.all_projects_info["parent-project"]["BUILD_TYPE"] == "release"

            # Check child project (should inherit from parent)
            assert "parent-project-child" in pm.all_projects_info
            child_config = pm.all_projects_info["parent-project-child"]
            assert (
                child_config["PROJECT_PO_CONFIG"] == "po_parent po_child"
            )  # Concatenated
            assert child_config["BUILD_TYPE"] == "release"  # Inherited from parent
            assert child_config["DEBUG_LEVEL"] == "high"  # Own config

    @patch("src.project_manager.path_from_root")
    def test_load_platform_plugin_operations(self, mock_path_from_root):
        """Test loading platform plugin operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create board directory with scripts
            board_dir = os.path.join(temp_dir, "test_board")
            scripts_dir = os.path.join(board_dir, "scripts")
            os.makedirs(scripts_dir)

            # Create a test script
            script_file = os.path.join(scripts_dir, "test_script.py")
            with open(script_file, "w", encoding="utf-8") as f:
                f.write("def test_function():\n")
                f.write("    pass\n")
                f.write("\n")
                f.write("def another_function():\n")
                f.write("    pass\n")

            mock_path_from_root.return_value = temp_dir
            pm = self.project_manager()

            assert "test_function" in pm.platform_operations
            assert "another_function" in pm.platform_operations

    @patch("src.project_manager.path_from_root")
    def test_load_builtin_plugin_operations(self, mock_path_from_root):
        """Test loading builtin plugin operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_path_from_root.return_value = temp_dir
            pm = self.project_manager()

            # Should have PatchOverride operations loaded
            assert len(pm.builtin_operations) > 0
            # Check for expected operations from PatchOverride
            expected_ops = ["po_apply", "po_revert", "po_new", "po_del"]
            for op in expected_ops:
                if op in pm.builtin_operations:
                    assert "func" in pm.builtin_operations[op]
                    assert "desc" in pm.builtin_operations[op]
                    assert "params" in pm.builtin_operations[op]

    def test_new_project_not_implemented(self):
        """Test that new_project method is not implemented."""
        pm = self.project_manager()
        # Should not raise an exception, just do nothing
        pm.new_project("test_project")

    def test_del_project_not_implemented(self):
        """Test that del_project method is not implemented."""
        pm = self.project_manager()
        # Should not raise an exception, just do nothing
        pm.del_project("test_project")

    def test_build_not_implemented(self):
        """Test that build method is not implemented."""
        pm = self.project_manager()
        # Should not raise an exception, just do nothing
        pm.build("test_project")

    def test_new_board_not_implemented(self):
        """Test that new_board method is not implemented."""
        pm = self.project_manager()
        # Should not raise an exception, just do nothing
        pm.new_board("test_board")

    def test_del_board_not_implemented(self):
        """Test that del_board method is not implemented."""
        pm = self.project_manager()
        # Should not raise an exception, just do nothing
        pm.del_board("test_board")


class TestMainFunction:
    """Test cases for main function."""

    def setup_method(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.project_manager import main

        self.main = main

    def test_main_version_argument(self):
        """Test main function with version argument."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "src", "--version"], capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "version" in result.stdout.lower() or result.stdout.strip() != ""

    @patch("src.project_manager.ProjectManager")
    @patch("src.project_manager.argparse.ArgumentParser")
    def test_main_build_operation(self, mock_parser_class, mock_pm_class):
        """Test main function with build operation."""
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

        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        # Use MagicMock instead of type() to ensure vars() works correctly
        mock_args = MagicMock()
        mock_args.operate = "build"
        mock_args.name = "test_project"
        mock_args.args = []
        mock_args.perf_analyze = False
        mock_parser.parse_args.return_value = mock_args
        mock_parser.parse_known_args.return_value = (mock_args, [])

        self.main()

        mock_pm_instance.build.assert_called_once_with(project_name="test_project")

    @patch("src.project_manager.ProjectManager")
    @patch("src.project_manager.argparse.ArgumentParser")
    def test_main_plugin_operation(self, mock_parser_class, mock_pm_class):
        """Test main function with plugin operation."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance

        # Mock builtin operations
        mock_pm_instance.builtin_operations = {
            "po_apply": {
                "func": MagicMock(),
                "param_count": 2,
                "required_count": 2,
                "desc": "Apply patch override",
                "params": ["project_name", "po_name"],
            }
        }

        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        # Use MagicMock instead of type() to ensure vars() works correctly
        mock_args = MagicMock()
        mock_args.operate = "po_apply"
        mock_args.name = "test_project"
        mock_args.args = ["po_test01"]
        mock_args.perf_analyze = False
        mock_parser.parse_args.return_value = mock_args
        mock_parser.parse_known_args.return_value = (mock_args, [])

        from src.project_manager import main

        main()

        # Verify the function was called with correct arguments
        mock_pm_instance.builtin_operations["po_apply"]["func"].assert_called_once_with(
            "test_project", "po_test01"
        )

    @patch("src.project_manager.ProjectManager")
    @patch("src.project_manager.argparse.ArgumentParser")
    def test_main_plugin_operation_insufficient_args(
        self, mock_parser_class, mock_pm_class
    ):
        """Test main function with insufficient arguments for plugin operation."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance

        # Mock builtin operations with required parameters
        mock_pm_instance.builtin_operations = {
            "po_apply": {
                "func": MagicMock(),
                "param_count": 2,
                "required_count": 2,
                "desc": "Apply patch override",
                "params": ["project_name", "po_name"],
            }
        }

        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        mock_args = MagicMock(
            operate="po_apply", name="test_project", args=[], perf_analyze=False
        )
        mock_parser.parse_args.return_value = mock_args
        mock_parser.parse_known_args.return_value = (mock_args, [])

        self.main()

        # Function should not be called due to insufficient arguments
        mock_pm_instance.builtin_operations["po_apply"]["func"].assert_not_called()

    @patch("src.project_manager.ProjectManager")
    @patch("src.project_manager.argparse.ArgumentParser")
    def test_main_unsupported_operation(self, mock_parser_class, mock_pm_class):
        """Test main function with unsupported operation."""
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

        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        mock_args = MagicMock(
            operate="unsupported_op", name="test_project", args=[], perf_analyze=False
        )
        mock_parser.parse_args.return_value = mock_args
        mock_parser.parse_known_args.return_value = (mock_args, [])

        self.main()

        # Should not raise exception, just log error
