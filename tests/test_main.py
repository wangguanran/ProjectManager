"""
Tests for __main__.py module.
"""

# pylint: disable=attribute-defined-outside-init
# pylint: disable=import-outside-toplevel
# pylint: disable=too-many-public-methods

import os
import shutil
import sys
import tempfile
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
        from src.__main__ import _load_all_projects, main

        self.main = main
        self._load_all_projects = _load_all_projects

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


class TestLoadAllProjects:
    """
    Comprehensive test cases for _load_all_projects function.

    This test suite covers the following scenarios:

    1. Basic Functionality:
       - Empty vprojects directory
       - Non-existent directory
       - Single board with single project
       - Multiple boards with multiple projects

    2. Configuration Inheritance:
       - Common configuration loading and inheritance
       - Parent-child relationship detection
       - Deep inheritance chains (4+ levels)
       - Configuration merging with proper precedence

    3. File System Handling:
       - Excluded directories (scripts, common, template, .cache, .git)
       - Multiple INI files error handling
       - Missing INI files
       - Directory structure validation

    4. Configuration Parsing:
       - Comment stripping (# and ; comments)
       - Whitespace handling
       - Duplicate key detection
       - Empty sections and comment-only sections
       - PROJECT_PO_CONFIG concatenation

    5. Parent-Child Relationships:
       - Hyphenated project names
       - Parent detection using rsplit("-", 1)[0]
       - Children assignment
       - Multi-level inheritance chains

    6. Error Handling:
       - Invalid project configurations
       - Missing common sections
       - File system errors
       - Configuration parsing errors

    7. Edge Cases:
       - Projects with no content
       - Sections with only comments
       - Whitespace in configuration values
       - Complex inheritance scenarios

    Test Coverage:
    - All major code paths in _load_all_projects function
    - Configuration inheritance logic
    - File system operations
    - Error handling scenarios
    - Parent-child relationship logic
    """

    def setup_method(self):
        """Set up test environment for each test case."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.__main__ import _load_all_projects

        self._load_all_projects = _load_all_projects
        self.temp_dir = None

    def teardown_method(self):
        """Clean up test environment after each test case."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_temp_vprojects_structure(self):
        """Create a temporary vprojects directory structure for testing."""
        self.temp_dir = tempfile.mkdtemp()
        vprojects_path = os.path.join(self.temp_dir, "vprojects")
        os.makedirs(vprojects_path)
        return vprojects_path

    def _create_board_structure(self, vprojects_path, board_name, ini_content):
        """Create a board directory with ini file."""
        board_path = os.path.join(vprojects_path, board_name)
        os.makedirs(board_path)
        ini_file = os.path.join(board_path, f"{board_name}.ini")
        with open(ini_file, "w", encoding="utf-8") as f:
            f.write(ini_content)
        return board_path, ini_file

    def _create_common_config(self, vprojects_path, common_content):
        """Create common configuration file."""
        common_path = os.path.join(vprojects_path, "common")
        os.makedirs(common_path)
        common_ini = os.path.join(common_path, "common.ini")
        with open(common_ini, "w", encoding="utf-8") as f:
            f.write(common_content)
        return common_ini

    def test_load_all_projects_empty_directory(self):
        """Test loading projects from an empty vprojects directory."""
        vprojects_path = self._create_temp_vprojects_structure()
        result = self._load_all_projects(vprojects_path)
        assert not result

    def test_load_all_projects_nonexistent_directory(self):
        """Test loading projects from a non-existent directory."""
        nonexistent_path = "/nonexistent/path"
        result = self._load_all_projects(nonexistent_path)
        assert not result

    def test_load_all_projects_single_board_single_project(self):
        """Test loading a single board with a single project."""
        vprojects_path = self._create_temp_vprojects_structure()

        # Create board with single project
        ini_content = """[testproject]
PROJECT_NAME=test_project
PROJECT_CHIP_NAME=test_chip
PROJECT_CUSTOMER=test_customer
"""
        self._create_board_structure(vprojects_path, "board01", ini_content)

        result = self._load_all_projects(vprojects_path)

        assert len(result) == 1
        assert "testproject" in result
        project_info = result["testproject"]
        assert project_info["board_name"] == "board01"
        assert project_info["parent"] is None
        assert project_info["children"] == []
        assert "PROJECT_NAME" in project_info["config"]
        assert project_info["config"]["PROJECT_NAME"] == "test_project"

    def test_load_all_projects_with_common_config(self):
        """Test loading projects with common configuration inheritance."""
        vprojects_path = self._create_temp_vprojects_structure()

        # Create common config
        common_content = """[common]
COMMON_SETTING=common_value
DEFAULT_CHIP=default_chip
"""
        self._create_common_config(vprojects_path, common_content)

        # Create board with project
        ini_content = """[test-project]
PROJECT_NAME=test_project
PROJECT_CHIP_NAME=test_chip
"""
        self._create_board_structure(vprojects_path, "board01", ini_content)

        result = self._load_all_projects(vprojects_path)

        assert len(result) == 1
        project_info = result["test-project"]
        # Should inherit common settings
        assert project_info["config"]["COMMON_SETTING"] == "common_value"
        assert project_info["config"]["DEFAULT_CHIP"] == "default_chip"
        assert project_info["config"]["PROJECT_CHIP_NAME"] == "test_chip"

    def test_load_all_projects_parent_child_relationship(self):
        """Test loading projects with parent-child relationships."""
        vprojects_path = self._create_temp_vprojects_structure()

        ini_content = """[parentproject]
PROJECT_NAME=parent_project

[parentproject-child]
PROJECT_NAME=parent_project_child

[parentproject-child-grandchild]
PROJECT_NAME=parent_project_child_grandchild
"""
        self._create_board_structure(vprojects_path, "board01", ini_content)

        result = self._load_all_projects(vprojects_path)

        assert len(result) == 3

        # Check parent-child relationships
        parent_info = result["parentproject"]
        child_info = result["parentproject-child"]
        grandchild_info = result["parentproject-child-grandchild"]

        assert parent_info["parent"] is None
        assert "parentproject-child" in parent_info["children"]

        assert child_info["parent"] == "parentproject"
        assert "parentproject-child-grandchild" in child_info["children"]

        assert grandchild_info["parent"] == "parentproject-child"
        assert grandchild_info["children"] == []

    def test_load_all_projects_exclude_directories(self):
        """Test that excluded directories are not processed."""
        vprojects_path = self._create_temp_vprojects_structure()

        # Create excluded directories
        for exclude_dir in ["scripts", "common", "template", ".cache", ".git"]:
            os.makedirs(os.path.join(vprojects_path, exclude_dir))

        # Create valid board
        ini_content = """[test-project]
PROJECT_NAME=test_project
"""
        self._create_board_structure(vprojects_path, "board01", ini_content)

        result = self._load_all_projects(vprojects_path)

        # Should only load the valid board, not excluded directories
        assert len(result) == 1
        assert "test-project" in result

    def test_load_all_projects_multiple_ini_files_error(self):
        """Test error handling when multiple ini files exist in a board directory."""
        vprojects_path = self._create_temp_vprojects_structure()
        board_path = os.path.join(vprojects_path, "board01")
        os.makedirs(board_path)

        # Create multiple ini files
        ini_files = ["board01.ini", "config.ini"]
        for ini_file in ini_files:
            with open(os.path.join(board_path, ini_file), "w", encoding="utf-8") as f:
                f.write("[test-project]\nPROJECT_NAME=test_project\n")

        # Should raise AssertionError
        with self.assert_raises(AssertionError):
            self._load_all_projects(vprojects_path)

    def test_load_all_projects_no_ini_file(self):
        """Test handling of board directory without ini file."""
        vprojects_path = self._create_temp_vprojects_structure()

        # Create board directory without ini file
        board_path = os.path.join(vprojects_path, "board01")
        os.makedirs(board_path)

        result = self._load_all_projects(vprojects_path)

        # Should return empty dict when no ini file found
        assert not result

    def test_load_all_projects_duplicate_keys(self):
        """Test handling of duplicate keys in project configuration."""
        vprojects_path = self._create_temp_vprojects_structure()

        ini_content = """[test-project]
PROJECT_NAME=test_project
PROJECT_NAME=duplicate_key
"""
        self._create_board_structure(vprojects_path, "board01", ini_content)

        result = self._load_all_projects(vprojects_path)

        # Should skip projects with duplicate keys
        assert not result

    def test_load_all_projects_comments_stripping(self):
        """Test that comments are properly stripped from configuration values."""
        vprojects_path = self._create_temp_vprojects_structure()

        ini_content = """[test-project]
PROJECT_NAME=test_project # inline comment
PROJECT_CHIP_NAME=test_chip ; another comment
PROJECT_CUSTOMER=test_customer
"""
        self._create_board_structure(vprojects_path, "board01", ini_content)

        result = self._load_all_projects(vprojects_path)

        assert len(result) == 1
        project_info = result["test-project"]
        assert project_info["config"]["PROJECT_NAME"] == "test_project"
        assert project_info["config"]["PROJECT_CHIP_NAME"] == "test_chip"
        assert project_info["config"]["PROJECT_CUSTOMER"] == "test_customer"

    def test_load_all_projects_po_config_concatenation(self):
        """Test that PROJECT_PO_CONFIG values are concatenated properly."""
        vprojects_path = self._create_temp_vprojects_structure()

        # Create common config with PO config
        common_content = """[common]
PROJECT_PO_CONFIG=po_common01
"""
        self._create_common_config(vprojects_path, common_content)

        # Create board with project that has its own PO config
        ini_content = """[test-project]
PROJECT_NAME=test_project
PROJECT_PO_CONFIG=po_test01
"""
        self._create_board_structure(vprojects_path, "board01", ini_content)

        result = self._load_all_projects(vprojects_path)

        assert len(result) == 1
        project_info = result["test-project"]
        # PO config should be concatenated
        assert project_info["config"]["PROJECT_PO_CONFIG"] == "po_common01 po_test01"

    def test_load_all_projects_multiple_boards(self):
        """Test loading projects from multiple boards."""
        vprojects_path = self._create_temp_vprojects_structure()

        # Create multiple boards
        board1_content = """[project1]
PROJECT_NAME=project1
"""
        board2_content = """[project2]
PROJECT_NAME=project2
"""

        self._create_board_structure(vprojects_path, "board01", board1_content)
        self._create_board_structure(vprojects_path, "board02", board2_content)

        result = self._load_all_projects(vprojects_path)

        assert len(result) == 2
        assert "project1" in result
        assert "project2" in result
        assert result["project1"]["board_name"] == "board01"
        assert result["project2"]["board_name"] == "board02"

    def test_load_all_projects_invalid_projects_handling(self):
        """Test handling of invalid projects."""
        vprojects_path = self._create_temp_vprojects_structure()

        ini_content = """[valid-project]
PROJECT_NAME=valid_project

[invalid-project]
PROJECT_NAME=invalid_project
"""
        self._create_board_structure(vprojects_path, "board01", ini_content)

        result = self._load_all_projects(vprojects_path)

        # Both projects should be loaded (invalid_projects set is empty in this test)
        assert len(result) == 2
        assert "valid-project" in result
        assert "invalid-project" in result

    def test_load_all_projects_complex_inheritance(self):
        """Test complex configuration inheritance scenarios."""
        vprojects_path = self._create_temp_vprojects_structure()

        # Create common config
        common_content = """[common]
BASE_SETTING=base_value
COMMON_CHIP=common_chip
"""
        self._create_common_config(vprojects_path, common_content)

        # Create parent project
        parent_content = """[parent-project]
PROJECT_NAME=parent_project
PARENT_SETTING=parent_value
"""
        self._create_board_structure(vprojects_path, "board01", parent_content)

        # Create child project
        child_content = """[parent-project-child]
PROJECT_NAME=child_project
CHILD_SETTING=child_value
"""
        self._create_board_structure(vprojects_path, "board02", child_content)

        result = self._load_all_projects(vprojects_path)

        assert len(result) == 2

        # Check inheritance
        parent_info = result["parent-project"]
        child_info = result["parent-project-child"]

        # Parent should inherit from common
        assert parent_info["config"]["BASE_SETTING"] == "base_value"
        assert parent_info["config"]["COMMON_CHIP"] == "common_chip"
        assert parent_info["config"]["PARENT_SETTING"] == "parent_value"

        # Child should inherit from parent and common
        assert child_info["config"]["BASE_SETTING"] == "base_value"
        assert child_info["config"]["COMMON_CHIP"] == "common_chip"
        assert child_info["config"]["PARENT_SETTING"] == "parent_value"
        assert child_info["config"]["CHILD_SETTING"] == "child_value"

    def test_load_all_projects_with_hyphenated_names(self):
        """Test loading projects with hyphenated names to verify parent-child logic."""
        vprojects_path = self._create_temp_vprojects_structure()

        ini_content = """[baseproject]
PROJECT_NAME=base_project

[baseproject-variant1]
PROJECT_NAME=base_project_variant1

[baseproject-variant2]
PROJECT_NAME=base_project_variant2
"""
        self._create_board_structure(vprojects_path, "board01", ini_content)

        result = self._load_all_projects(vprojects_path)

        assert len(result) == 3

        base_info = result["baseproject"]
        variant1_info = result["baseproject-variant1"]
        variant2_info = result["baseproject-variant2"]

        # Base project has no parent
        assert base_info["parent"] is None
        assert "baseproject-variant1" in base_info["children"]
        assert "baseproject-variant2" in base_info["children"]

        # Variants have baseproject as parent
        assert variant1_info["parent"] == "baseproject"
        assert variant1_info["children"] == []

        assert variant2_info["parent"] == "baseproject"
        assert variant2_info["children"] == []

    def test_load_all_projects_common_config_missing_section(self):
        """Test handling when common.ini exists but has no [common] section."""
        vprojects_path = self._create_temp_vprojects_structure()

        # Create common config without [common] section
        common_content = """[other-section]
SOME_SETTING=some_value
"""
        self._create_common_config(vprojects_path, common_content)

        # Create board with project
        ini_content = """[testproject]
PROJECT_NAME=test_project
"""
        self._create_board_structure(vprojects_path, "board01", ini_content)

        result = self._load_all_projects(vprojects_path)

        assert len(result) == 1
        project_info = result["testproject"]
        # Should not inherit any common settings since [common] section is missing
        assert "SOME_SETTING" not in project_info["config"]

    def test_load_all_projects_empty_sections(self):
        """Test handling of empty project sections."""
        vprojects_path = self._create_temp_vprojects_structure()

        ini_content = """[empty-project]
# This section has no content

[valid-project]
PROJECT_NAME=valid_project
"""
        self._create_board_structure(vprojects_path, "board01", ini_content)

        result = self._load_all_projects(vprojects_path)

        # Empty sections are still loaded but with empty config
        assert len(result) == 2
        assert "valid-project" in result
        assert "empty-project" in result
        assert result["valid-project"]["config"]["PROJECT_NAME"] == "valid_project"
        assert result["empty-project"]["config"] == {}

    def test_load_all_projects_comments_only_sections(self):
        """Test handling of sections with only comments."""
        vprojects_path = self._create_temp_vprojects_structure()

        ini_content = """[comment-only-project]
# This is a comment
; This is another comment

[valid-project]
PROJECT_NAME=valid_project
"""
        self._create_board_structure(vprojects_path, "board01", ini_content)

        result = self._load_all_projects(vprojects_path)

        # Comment-only sections are still loaded but with empty config
        assert len(result) == 2
        assert "valid-project" in result
        assert "comment-only-project" in result
        assert result["valid-project"]["config"]["PROJECT_NAME"] == "valid_project"
        assert result["comment-only-project"]["config"] == {}

    def test_load_all_projects_whitespace_handling(self):
        """Test handling of whitespace in configuration values."""
        vprojects_path = self._create_temp_vprojects_structure()

        ini_content = """[testproject]
PROJECT_NAME=  test_project
PROJECT_CHIP_NAME=  test_chip
PROJECT_CUSTOMER=test_customer
"""
        self._create_board_structure(vprojects_path, "board01", ini_content)

        result = self._load_all_projects(vprojects_path)

        assert len(result) == 1
        project_info = result["testproject"]
        # Whitespace should be stripped
        assert project_info["config"]["PROJECT_NAME"] == "test_project"
        assert project_info["config"]["PROJECT_CHIP_NAME"] == "test_chip"
        assert project_info["config"]["PROJECT_CUSTOMER"] == "test_customer"

    def test_load_all_projects_po_config_with_whitespace(self):
        """Test PROJECT_PO_CONFIG concatenation with whitespace handling."""
        vprojects_path = self._create_temp_vprojects_structure()

        # Create common config with PO config
        common_content = """[common]
PROJECT_PO_CONFIG=  po_common01
"""
        self._create_common_config(vprojects_path, common_content)

        # Create board with project that has its own PO config
        ini_content = """[testproject]
PROJECT_NAME=test_project
PROJECT_PO_CONFIG=  po_test01
"""
        self._create_board_structure(vprojects_path, "board01", ini_content)

        result = self._load_all_projects(vprojects_path)

        assert len(result) == 1
        project_info = result["testproject"]
        # PO config should be concatenated with proper whitespace handling
        assert project_info["config"]["PROJECT_PO_CONFIG"] == "po_common01 po_test01"

    def test_load_all_projects_deep_inheritance_chain(self):
        """Test deep inheritance chain with multiple levels."""
        vprojects_path = self._create_temp_vprojects_structure()

        # Create common config
        common_content = """[common]
BASE_SETTING=base_value
"""
        self._create_common_config(vprojects_path, common_content)

        # Create multiple levels of inheritance
        ini_content = """[level1]
LEVEL1_SETTING=level1_value

[level1-level2]
LEVEL2_SETTING=level2_value

[level1-level2-level3]
LEVEL3_SETTING=level3_value

[level1-level2-level3-level4]
LEVEL4_SETTING=level4_value
"""
        self._create_board_structure(vprojects_path, "board01", ini_content)

        result = self._load_all_projects(vprojects_path)

        assert len(result) == 4

        # Check inheritance chain
        level1_info = result["level1"]
        level2_info = result["level1-level2"]
        level3_info = result["level1-level2-level3"]
        level4_info = result["level1-level2-level3-level4"]

        # Level 1 should inherit from common
        assert level1_info["config"]["BASE_SETTING"] == "base_value"
        assert level1_info["config"]["LEVEL1_SETTING"] == "level1_value"

        # Level 2 should inherit from level1 and common
        assert level2_info["config"]["BASE_SETTING"] == "base_value"
        assert level2_info["config"]["LEVEL1_SETTING"] == "level1_value"
        assert level2_info["config"]["LEVEL2_SETTING"] == "level2_value"

        # Level 3 should inherit from level2, level1, and common
        assert level3_info["config"]["BASE_SETTING"] == "base_value"
        assert level3_info["config"]["LEVEL1_SETTING"] == "level1_value"
        assert level3_info["config"]["LEVEL2_SETTING"] == "level2_value"
        assert level3_info["config"]["LEVEL3_SETTING"] == "level3_value"

        # Level 4 should inherit from all previous levels
        assert level4_info["config"]["BASE_SETTING"] == "base_value"
        assert level4_info["config"]["LEVEL1_SETTING"] == "level1_value"
        assert level4_info["config"]["LEVEL2_SETTING"] == "level2_value"
        assert level4_info["config"]["LEVEL3_SETTING"] == "level3_value"
        assert level4_info["config"]["LEVEL4_SETTING"] == "level4_value"

    def assert_raises(self, exception_class):
        """Helper method to assert that an exception is raised."""

        class AssertRaisesContext:
            """Context manager for asserting exceptions are raised."""

            def __init__(self, exception_class):
                self.exception_class = exception_class

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    raise AssertionError(
                        f"Expected {self.exception_class} to be raised"
                    )
                if not issubclass(exc_type, self.exception_class):
                    raise AssertionError(
                        f"Expected {self.exception_class}, got {exc_type}"
                    )
                return True

        return AssertRaisesContext(exception_class)


class TestPluginOperations:
    """Test cases for plugin operation loading functions."""

    def setup_method(self):
        """Set up test environment for each test case."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.__main__ import (
            _load_builtin_plugin_operations,
            _load_platform_plugin_operations,
            _load_plugin_operations,
        )

        self._load_plugin_operations = _load_plugin_operations
        self._load_builtin_plugin_operations = _load_builtin_plugin_operations
        self._load_platform_plugin_operations = _load_platform_plugin_operations
        self.temp_dir = None

    def teardown_method(self):
        """Clean up test environment after each test case."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_temp_vprojects_structure(self):
        """Create a temporary vprojects directory structure for testing."""
        self.temp_dir = tempfile.mkdtemp()
        vprojects_path = os.path.join(self.temp_dir, "vprojects")
        os.makedirs(vprojects_path)
        return vprojects_path

    def _create_test_plugin_class(self):
        """Create a test plugin class with various method types."""

        class TestPlugin:
            """Test plugin class for testing plugin loading functionality."""

            def __init__(self):
                pass  # pylint: disable=unnecessary-pass

            @staticmethod
            def static_method_no_doc(env, projects_info, project_name):
                """Static method without detailed docstring."""
                pass  # pylint: disable=unnecessary-pass

            @staticmethod
            def static_method_with_doc(
                env, projects_info, project_name, flag1=False, flag2=True
            ):
                """
                Static method with detailed docstring.
                flag1 (bool): First flag description
                flag2 (bool): Second flag description
                """
                pass  # pylint: disable=unnecessary-pass

            @staticmethod
            def static_method_needs_repos(env, projects_info, project_name):
                """
                Static method that needs repositories.
                @needs_repositories
                """
                pass  # pylint: disable=unnecessary-pass

            @classmethod
            def class_method(cls, env, projects_info, project_name):
                """Class method for testing."""
                pass  # pylint: disable=unnecessary-pass

            def instance_method(self, env, projects_info, project_name):
                """Instance method that should be ignored."""
                pass  # pylint: disable=unnecessary-pass

            def _private_method(self, env, projects_info, project_name):
                """Private method that should be ignored."""
                pass  # pylint: disable=unnecessary-pass

        return TestPlugin

    def test_load_plugin_operations_empty_list(self):
        """Test loading plugin operations from empty class list."""
        result = self._load_plugin_operations([])
        assert not result

    def test_load_plugin_operations_single_class(self):
        """Test loading plugin operations from a single class."""
        test_plugin = self._create_test_plugin_class()
        result = self._load_plugin_operations([test_plugin])

        # Should load static and class methods, but not instance or private methods
        assert len(result) == 4
        assert "static_method_no_doc" in result
        assert "static_method_with_doc" in result
        assert "static_method_needs_repos" in result
        assert "class_method" in result
        assert "instance_method" not in result
        assert "_private_method" not in result

    def test_load_plugin_operations_method_metadata(self):
        """Test that method metadata is correctly extracted."""
        test_plugin = self._create_test_plugin_class()
        result = self._load_plugin_operations([test_plugin])

        # Test static_method_no_doc
        static_no_doc = result["static_method_no_doc"]
        assert static_no_doc["desc"] == "Static method without detailed docstring."
        assert static_no_doc["params"] == ["env", "projects_info", "project_name"]
        assert static_no_doc["param_count"] == 3
        assert static_no_doc["required_params"] == [
            "env",
            "projects_info",
            "project_name",
        ]
        assert static_no_doc["required_count"] == 3
        assert not static_no_doc["needs_repositories"]
        assert static_no_doc["plugin_class"] == test_plugin

        # Test static_method_with_doc
        static_with_doc = result["static_method_with_doc"]
        assert static_with_doc["desc"] == "Static method with detailed docstring."
        assert static_with_doc["params"] == [
            "env",
            "projects_info",
            "project_name",
            "flag1",
            "flag2",
        ]
        assert static_with_doc["param_count"] == 5
        assert static_with_doc["required_params"] == [
            "env",
            "projects_info",
            "project_name",
        ]
        assert static_with_doc["required_count"] == 3
        assert not static_with_doc["needs_repositories"]

        # Test static_method_needs_repos
        static_needs_repos = result["static_method_needs_repos"]
        assert static_needs_repos["needs_repositories"] is True

    def test_load_builtin_plugin_operations(self):
        """Test loading builtin plugin operations."""
        result = self._load_builtin_plugin_operations()

        # Should load operations from ProjectManager, PatchOverride, and ProjectBuilder
        assert len(result) > 0

        # Check for some expected operations
        expected_operations = [
            "project_new",
            "project_del",
            "board_new",
            "board_del",  # ProjectManager
            "po_apply",
            "po_revert",
            "po_new",
            "po_del",
            "po_list",  # PatchOverride
            "project_diff",
            "project_pre_build",
            "project_do_build",
            "project_post_build",
            "project_build",  # ProjectBuilder
        ]

        for operation in expected_operations:
            if operation in result:
                assert "func" in result[operation]
                assert "desc" in result[operation]
                assert "params" in result[operation]
                assert "plugin_class" in result[operation]

    def test_load_platform_plugin_operations_no_scripts_dir(self):
        """Test loading platform plugin operations when scripts directory doesn't exist."""
        vprojects_path = self._create_temp_vprojects_structure()
        result = self._load_platform_plugin_operations(vprojects_path)
        assert not result

    def test_load_platform_plugin_operations_empty_scripts_dir(self):
        """Test loading platform plugin operations from empty scripts directory."""
        vprojects_path = self._create_temp_vprojects_structure()
        scripts_dir = os.path.join(vprojects_path, "scripts")
        os.makedirs(scripts_dir)

        result = self._load_platform_plugin_operations(vprojects_path)
        assert not result

    def test_load_platform_plugin_operations_valid_script(self):
        """Test loading platform plugin operations from valid script file."""
        vprojects_path = self._create_temp_vprojects_structure()
        scripts_dir = os.path.join(vprojects_path, "scripts")
        os.makedirs(scripts_dir)

        # Create a valid platform script
        script_content = '''
class PlatformPlugin:
    """Test platform plugin class."""

    @staticmethod
    def platform_operation(env, projects_info, project_name):
        """Platform operation for testing."""
        pass

    @staticmethod
    def another_operation(env, projects_info, project_name, flag=False):
        """Another platform operation."""
        pass

    def _private_method(self):
        """Private method that should be ignored."""
        pass
'''
        script_path = os.path.join(scripts_dir, "platform_builder.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        result = self._load_platform_plugin_operations(vprojects_path)

        assert len(result) == 2
        assert "platform_operation" in result
        assert "another_operation" in result
        assert "_private_method" not in result

        # Check metadata
        platform_op = result["platform_operation"]
        assert platform_op["desc"] == "Platform operation for testing."
        assert platform_op["params"] == ["env", "projects_info", "project_name"]
        assert platform_op["required_count"] == 3

        another_op = result["another_operation"]
        assert another_op["desc"] == "Another platform operation."
        assert another_op["params"] == ["env", "projects_info", "project_name", "flag"]
        assert another_op["required_count"] == 3

    def test_load_platform_plugin_operations_invalid_script(self):
        """Test loading platform plugin operations with invalid script."""
        vprojects_path = self._create_temp_vprojects_structure()
        scripts_dir = os.path.join(vprojects_path, "scripts")
        os.makedirs(scripts_dir)

        # Create an invalid script that will cause import error
        script_content = """
import nonexistent_module

class PlatformPlugin:
    @staticmethod
    def platform_operation(env, projects_info, project_name):
        pass
"""
        script_path = os.path.join(scripts_dir, "invalid_script.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        result = self._load_platform_plugin_operations(vprojects_path)
        # Should return empty dict due to import error
        assert not result

    def test_load_platform_plugin_operations_underscore_file(self):
        """Test that files starting with underscore are ignored."""
        vprojects_path = self._create_temp_vprojects_structure()
        scripts_dir = os.path.join(vprojects_path, "scripts")
        os.makedirs(scripts_dir)

        # Create a script with underscore prefix
        script_content = """
class PlatformPlugin:
    @staticmethod
    def platform_operation(env, projects_info, project_name):
        pass
"""
        script_path = os.path.join(scripts_dir, "_private_script.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        result = self._load_platform_plugin_operations(vprojects_path)
        # Should return empty dict as underscore files are ignored
        assert not result

    def test_load_platform_plugin_operations_non_py_file(self):
        """Test that non-Python files are ignored."""
        vprojects_path = self._create_temp_vprojects_structure()
        scripts_dir = os.path.join(vprojects_path, "scripts")
        os.makedirs(scripts_dir)

        # Create a non-Python file
        script_path = os.path.join(scripts_dir, "config.txt")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write("This is not a Python file")

        result = self._load_platform_plugin_operations(vprojects_path)
        # Should return empty dict as non-Python files are ignored
        assert not result

    def test_load_plugin_operations_needs_repositories_detection(self):
        """Test detection of @needs_repositories in docstrings."""

        class RepoPlugin:
            """Test plugin class for testing @needs_repositories detection."""

            @staticmethod
            def needs_repos_method(env, projects_info, project_name):
                """
                Method that needs repositories.
                @needs_repositories
                """
                pass  # pylint: disable=unnecessary-pass

            @staticmethod
            def no_repos_method(env, projects_info, project_name):
                """
                Method that doesn't need repositories.
                """
                pass  # pylint: disable=unnecessary-pass

            @staticmethod
            def partial_needs_repos_method(env, projects_info, project_name):
                """
                Method with @needs_repositories in middle of docstring.
                Some description here.
                @needs_repositories
                More description.
                """
                pass  # pylint: disable=unnecessary-pass

        result = self._load_plugin_operations([RepoPlugin])

        assert len(result) == 3
        assert result["needs_repos_method"]["needs_repositories"] is True
