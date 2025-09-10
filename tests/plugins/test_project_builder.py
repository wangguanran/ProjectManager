"""
Tests for project_builder functions.
"""

import os
import sys
import tarfile
from unittest.mock import MagicMock, patch


class TestProjectDiff:
    """Test cases for project_diff function."""

    def setup_method(self):
        """
        Prepare the test environment for each test case.
        - Adds the project root to sys.path if not already present, ensuring modules can be imported correctly.
        - Imports the function/class from src.plugins.project_builder and assigns it to self.project_diff for use in test cases.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.plugins.project_builder import project_diff

        self.project_diff = project_diff

    def test_project_diff_basic_functionality(self):
        """Test project_diff with basic functionality"""
        # Arrange
        env = {"repositories": []}
        projects_info = {}
        project_name = "test_project"
        keep_diff_dir = False

        # Act
        result = self.project_diff(env, projects_info, project_name, keep_diff_dir)

        # Assert
        assert result is True

    def test_project_diff_with_keep_diff_dir_true(self):
        """Test project_diff with keep_diff_dir=True flag"""
        # Arrange
        env = {"repositories": []}
        projects_info = {}
        project_name = "test_project"
        keep_diff_dir = True

        # Act
        result = self.project_diff(env, projects_info, project_name, keep_diff_dir)

        # Assert
        assert result is True

    def test_project_diff_with_keep_diff_dir_false(self):
        """Test project_diff with keep_diff_dir=False flag (default behavior)"""
        # Arrange
        env = {"repositories": []}
        projects_info = {}
        project_name = "test_project"
        keep_diff_dir = False

        # Act
        result = self.project_diff(env, projects_info, project_name, keep_diff_dir)

        # Assert
        assert result is True

    def test_project_diff_empty_project_name(self):
        """Test project_diff with empty project name"""
        # Arrange
        env = {"repositories": []}
        projects_info = {}
        project_name = ""
        keep_diff_dir = False

        # Act
        result = self.project_diff(env, projects_info, project_name, keep_diff_dir)

        # Assert
        assert result is True

    def test_project_diff_none_projects_info(self):
        """Test project_diff with None projects_info"""
        # Arrange
        env = {"repositories": []}
        projects_info = None
        project_name = "test_project"
        keep_diff_dir = False

        # Act
        result = self.project_diff(env, projects_info, project_name, keep_diff_dir)

        # Assert
        assert result is True

    def test_project_diff_single_repository(self):
        """Test project_diff with single repository"""
        # Arrange
        env = {"repositories": [("/tmp/repo1", "repo1")]}
        projects_info = {}
        project_name = "test_project"
        keep_diff_dir = False

        # Mock subprocess calls to avoid actual git operations
        with patch("src.plugins.project_builder.subprocess.check_output") as mock_check_output, patch(
            "src.plugins.project_builder.subprocess.run"
        ) as mock_run, patch("src.plugins.project_builder.os.chdir") as mock_chdir:

            # Mock git commands
            mock_check_output.return_value = b""
            mock_run.return_value = MagicMock(returncode=0)
            mock_chdir.return_value = None

            # Act
            result = self.project_diff(env, projects_info, project_name, keep_diff_dir)

            # Assert
            assert result is True

    def test_project_diff_multiple_repositories(self):
        """Test project_diff with multiple repositories"""
        # Arrange
        env = {"repositories": [("/tmp/repo1", "repo1"), ("/tmp/repo2", "repo2")]}
        projects_info = {}
        project_name = "test_project"
        keep_diff_dir = False

        # Mock subprocess calls to avoid actual git operations
        with patch("src.plugins.project_builder.subprocess.check_output") as mock_check_output, patch(
            "src.plugins.project_builder.subprocess.run"
        ) as mock_run, patch("src.plugins.project_builder.os.chdir") as mock_chdir:

            # Mock git commands
            mock_check_output.return_value = b""
            mock_run.return_value = MagicMock(returncode=0)
            mock_chdir.return_value = None

            # Act
            result = self.project_diff(env, projects_info, project_name, keep_diff_dir)

            # Assert
            assert result is True

    def test_project_diff_special_characters_in_project_name(self):
        """Test project_diff with special characters in project name"""
        # Arrange
        env = {"repositories": []}
        projects_info = {}
        project_name = "test@project#123"
        keep_diff_dir = False

        # Act
        result = self.project_diff(env, projects_info, project_name, keep_diff_dir)

        # Assert
        assert result is True

    def test_project_diff_very_long_project_name(self):
        """Test project_diff with very long project name"""
        # Arrange
        env = {"repositories": []}
        projects_info = {}
        project_name = "a" * 100  # Use reasonable length
        keep_diff_dir = False

        # Act
        result = self.project_diff(env, projects_info, project_name, keep_diff_dir)

        # Assert
        assert result is True

    @patch("src.plugins.project_builder.tarfile.open")
    def test_project_diff_tarfile_creation_success(self, mock_tarfile):
        """Test project_diff tarfile creation success"""
        # Arrange
        mock_tar = MagicMock()
        mock_tarfile.return_value.__enter__.return_value = mock_tar
        env = {"repositories": []}
        projects_info = {}
        project_name = "test_project"
        keep_diff_dir = False

        # Act
        result = self.project_diff(env, projects_info, project_name, keep_diff_dir)

        # Assert
        assert result is True
        mock_tarfile.assert_called_once()

    @patch("src.plugins.project_builder.tarfile.open")
    def test_project_diff_tarfile_creation_failure(self, mock_tarfile):
        """Test project_diff tarfile creation failure"""
        # Arrange
        mock_tarfile.side_effect = tarfile.TarError("Tarfile creation failed")
        env = {"repositories": []}
        projects_info = {}
        project_name = "test_project"
        keep_diff_dir = False

        # Act
        result = self.project_diff(env, projects_info, project_name, keep_diff_dir)

        # Assert
        assert result is True  # Function should continue even if archiving fails
        # Verify that tarfile.open was called
        mock_tarfile.assert_called()

    @patch("src.plugins.project_builder.shutil.rmtree")
    def test_project_diff_remove_directory_success(self, mock_rmtree):
        """Test project_diff removes directory when keep_diff_dir=False"""
        # Arrange
        env = {"repositories": []}
        projects_info = {}
        project_name = "test_project"
        keep_diff_dir = False

        # Act
        result = self.project_diff(env, projects_info, project_name, keep_diff_dir)

        # Assert
        assert result is True
        # Check that the main diff directory was removed (last call)
        main_diff_dir_call = mock_rmtree.call_args_list[-1]
        assert "diff" in str(main_diff_dir_call)

    @patch("src.plugins.project_builder.shutil.rmtree")
    def test_project_diff_keep_directory_when_flag_true(self, mock_rmtree):
        """Test project_diff keeps directory when keep_diff_dir=True"""
        # Arrange
        env = {"repositories": []}
        projects_info = {}
        project_name = "test_project"
        keep_diff_dir = True

        # Act
        result = self.project_diff(env, projects_info, project_name, keep_diff_dir)

        # Assert
        assert result is True
        # Check that the main diff directory was NOT removed
        # The function still calls rmtree for subdirectories, but not for the main diff directory
        main_diff_dir_removed = any(
            "diff" in str(call)
            and "after" not in str(call)
            and "before" not in str(call)
            and "patch" not in str(call)
            and "commit" not in str(call)
            for call in mock_rmtree.call_args_list
        )
        assert not main_diff_dir_removed


class TestProjectPreBuild:
    """Test cases for project_pre_build function."""

    def setup_method(self):
        """
        Prepare the test environment for each test case.
        - Adds the project root to sys.path if not already present, ensuring modules can be imported correctly.
        - Imports the function/class from src.plugins.project_builder and assigns it to self.project_pre_build for use in test cases.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.plugins.project_builder import project_pre_build

        self.project_pre_build = project_pre_build

    @patch("src.plugins.project_builder.po_apply")
    @patch("src.plugins.project_builder.project_diff")
    def test_project_pre_build_basic_functionality(self, mock_project_diff, mock_po_apply):
        """Test project_pre_build basic functionality"""
        # Arrange
        mock_project_diff.return_value = True
        mock_po_apply.return_value = True
        env = {}
        projects_info = {}
        project_name = "test_project"

        # Act
        result = self.project_pre_build(env, projects_info, project_name)

        # Assert
        assert result is True
        mock_project_diff.assert_called_once_with(env, projects_info, project_name)
        mock_po_apply.assert_called_once_with(env, projects_info, project_name)

    @patch("src.plugins.project_builder.po_apply")
    @patch("src.plugins.project_builder.project_diff")
    def test_project_pre_build_project_diff_failure(self, mock_project_diff, mock_po_apply):
        """Test project_pre_build when project_diff fails"""
        # Arrange
        mock_project_diff.return_value = False
        mock_po_apply.return_value = True
        env = {}
        projects_info = {}
        project_name = "test_project"

        # Act
        result = self.project_pre_build(env, projects_info, project_name)

        # Assert
        # Note: project_pre_build always returns True regardless of project_diff result
        assert result is True
        mock_project_diff.assert_called_once_with(env, projects_info, project_name)
        mock_po_apply.assert_called_once_with(env, projects_info, project_name)


class TestProjectDoBuild:
    """Test cases for project_do_build function."""

    def setup_method(self):
        """
        Prepare the test environment for each test case.
        - Adds the project root to sys.path if not already present, ensuring modules can be imported correctly.
        - Imports the function/class from src.plugins.project_builder and assigns it to self.project_do_build for use in test cases.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.plugins.project_builder import project_do_build

        self.project_do_build = project_do_build

    def test_project_do_build_basic_functionality(self):
        """Test project_do_build basic functionality"""
        # Arrange
        env = {}
        projects_info = {}
        project_name = "test_project"

        # Act
        result = self.project_do_build(env, projects_info, project_name)

        # Assert
        assert result is True

    def test_project_do_build_empty_project_name(self):
        """Test project_do_build with empty project name"""
        # Arrange
        env = {}
        projects_info = {}
        project_name = ""

        # Act
        result = self.project_do_build(env, projects_info, project_name)

        # Assert
        assert result is True

    def test_project_do_build_none_projects_info(self):
        """Test project_do_build with None projects_info"""
        # Arrange
        env = {}
        projects_info = None
        project_name = "test_project"

        # Act
        result = self.project_do_build(env, projects_info, project_name)

        # Assert
        assert result is True

    def test_project_do_build_complex_env(self):
        """Test project_do_build with complex environment"""
        # Arrange
        env = {"key1": "value1", "key2": ["item1", "item2"], "key3": {"nested": "value"}}
        projects_info = {"project1": {"config": {"key": "value"}}}
        project_name = "test_project"

        # Act
        result = self.project_do_build(env, projects_info, project_name)

        # Assert
        assert result is True


class TestProjectPostBuild:
    """Test cases for project_post_build function."""

    def setup_method(self):
        """
        Prepare the test environment for each test case.
        - Adds the project root to sys.path if not already present, ensuring modules can be imported correctly.
        - Imports the function/class from src.plugins.project_builder and assigns it to self.project_post_build for use in test cases.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.plugins.project_builder import project_post_build

        self.project_post_build = project_post_build

    def test_project_post_build_basic_functionality(self):
        """Test project_post_build basic functionality"""
        # Arrange
        env = {}
        projects_info = {}
        project_name = "test_project"

        # Act
        result = self.project_post_build(env, projects_info, project_name)

        # Assert
        assert result is True

    def test_project_post_build_empty_project_name(self):
        """Test project_post_build with empty project name"""
        # Arrange
        env = {}
        projects_info = {}
        project_name = ""

        # Act
        result = self.project_post_build(env, projects_info, project_name)

        # Assert
        assert result is True

    def test_project_post_build_none_projects_info(self):
        """Test project_post_build with None projects_info"""
        # Arrange
        env = {}
        projects_info = None
        project_name = "test_project"

        # Act
        result = self.project_post_build(env, projects_info, project_name)

        # Assert
        assert result is True


class TestProjectBuild:
    """Test cases for project_build function."""

    def setup_method(self):
        """
        Prepare the test environment for each test case.
        - Adds the project root to sys.path if not already present, ensuring modules can be imported correctly.
        - Imports the function/class from src.plugins.project_builder and assigns it to self.project_build for use in test cases.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.plugins.project_builder import project_build

        self.project_build = project_build

    @patch("src.plugins.project_builder.project_pre_build")
    @patch("src.plugins.project_builder.project_do_build")
    @patch("src.plugins.project_builder.project_post_build")
    def test_project_build_basic_functionality(self, mock_post_build, mock_do_build, mock_pre_build):
        """Test project_build basic functionality"""
        # Arrange
        mock_pre_build.return_value = True
        mock_do_build.return_value = True
        mock_post_build.return_value = True
        env = {}
        projects_info = {}
        project_name = "test_project"

        # Act
        result = self.project_build(env, projects_info, project_name)

        # Assert
        assert result is True
        mock_pre_build.assert_called_once_with(env, projects_info, project_name)
        mock_do_build.assert_called_once_with(env, projects_info, project_name)
        mock_post_build.assert_called_once_with(env, projects_info, project_name)

    @patch("src.plugins.project_builder.project_pre_build")
    def test_project_build_pre_build_failure(self, mock_pre_build):
        """Test project_build when pre_build fails"""
        # Arrange
        mock_pre_build.return_value = False
        env = {}
        projects_info = {}
        project_name = "test_project"

        # Act
        result = self.project_build(env, projects_info, project_name)

        # Assert
        assert result is False
        mock_pre_build.assert_called_once_with(env, projects_info, project_name)

    @patch("src.plugins.project_builder.project_pre_build")
    @patch("src.plugins.project_builder.project_do_build")
    def test_project_build_do_build_failure(self, mock_do_build, mock_pre_build):
        """Test project_build when do_build fails"""
        # Arrange
        mock_pre_build.return_value = True
        mock_do_build.return_value = False
        env = {}
        projects_info = {}
        project_name = "test_project"

        # Act
        result = self.project_build(env, projects_info, project_name)

        # Assert
        assert result is False
        mock_pre_build.assert_called_once_with(env, projects_info, project_name)
        mock_do_build.assert_called_once_with(env, projects_info, project_name)

    @patch("src.plugins.project_builder.project_pre_build")
    @patch("src.plugins.project_builder.project_do_build")
    @patch("src.plugins.project_builder.project_post_build")
    def test_project_build_post_build_failure(self, mock_post_build, mock_do_build, mock_pre_build):
        """Test project_build when post_build fails"""
        # Arrange
        mock_pre_build.return_value = True
        mock_do_build.return_value = True
        mock_post_build.return_value = False
        env = {}
        projects_info = {}
        project_name = "test_project"

        # Act
        result = self.project_build(env, projects_info, project_name)

        # Assert
        assert result is False
        mock_pre_build.assert_called_once_with(env, projects_info, project_name)
        mock_do_build.assert_called_once_with(env, projects_info, project_name)
        mock_post_build.assert_called_once_with(env, projects_info, project_name)

    @patch("src.plugins.project_builder.po_apply")
    def test_project_build_with_platform_config(self, mock_po_apply):
        """Test project_build with platform configuration"""
        # Arrange
        env = {}
        projects_info = {"test_project": {"config": {"PROJECT_PLATFORM": "linux"}}}
        project_name = "test_project"

        # Act
        mock_po_apply.return_value = True
        result = self.project_build(env, projects_info, project_name)

        # Assert
        assert result is True

    @patch("src.plugins.project_builder.po_apply")
    def test_project_build_without_platform_config(self, mock_po_apply):
        """Test project_build without platform configuration"""
        # Arrange
        env = {}
        projects_info = {"test_project": {"config": {}}}
        project_name = "test_project"
        mock_po_apply.return_value = True

        # Act
        result = self.project_build(env, projects_info, project_name)

        # Assert
        assert result is True

    @patch("src.plugins.project_builder.po_apply")
    def test_project_build_empty_projects_info(self, mock_po_apply):
        """Test project_build with empty projects_info"""
        # Arrange
        env = {}
        projects_info = {}
        project_name = "test_project"
        mock_po_apply.return_value = True

        # Act
        result = self.project_build(env, projects_info, project_name)

        # Assert
        assert result is True

    def test_project_build_nonexistent_project(self):
        """Test project_build with nonexistent project"""
        # Arrange
        env = {}
        projects_info = {}
        project_name = "nonexistent_project"

        # Act
        with patch("src.plugins.project_builder.po_apply") as mock_po_apply:
            mock_po_apply.return_value = True
            result = self.project_build(env, projects_info, project_name)

        # Assert
        assert result is True

    @patch("src.plugins.project_builder.po_apply")
    def test_project_build_empty_project_name(self, mock_po_apply):
        """Test project_build with empty project name"""
        # Arrange
        env = {}
        projects_info = {}
        project_name = ""
        mock_po_apply.return_value = True

        # Act
        result = self.project_build(env, projects_info, project_name)

        # Assert
        assert result is True
