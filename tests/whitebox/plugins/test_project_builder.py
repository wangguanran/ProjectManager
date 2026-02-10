"""
Tests for project_builder functions.
"""

import os
import subprocess
import sys
import tarfile
from unittest.mock import MagicMock, patch

# Tests intentionally patch internal hook registry state.
# pylint: disable=protected-access


class TestProjectDiff:
    """Test cases for project_diff function."""

    def setup_method(self):
        """
        Prepare the test environment for each test case.
        - Adds the project root to sys.path if not already present, ensuring modules can be imported correctly.
        - Imports the function/class from src.plugins.project_builder and assigns it to self.project_diff for use in test cases.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
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

    def test_project_diff_dry_run_does_not_create_cache(self, tmp_path, monkeypatch):
        """DRY-001: project_diff --dry-run does not create .cache/build diff directories."""
        monkeypatch.chdir(tmp_path)
        env = {"repositories": []}
        projects_info = {}
        result = self.project_diff(env, projects_info, "test_project", keep_diff_dir=False, dry_run=True)
        assert result is True
        assert not (tmp_path / ".cache").exists()

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

    def test_project_diff_single_repo_archive_structure_real_git(self, tmp_path):
        """BUILD-001: Single repo diff archive contains after/before/patch/commit without repo subdir."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir(parents=True, exist_ok=True)

        def _git(*args: str) -> None:
            subprocess.run(
                ["git", *args], cwd=str(repo_root), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        _git("init")
        _git("config", "user.email", "test@example.com")
        _git("config", "user.name", "Test User")

        (repo_root / "a.txt").write_text("base\n", encoding="utf-8")
        _git("add", "a.txt")
        _git("commit", "-m", "base")

        # Create a worktree change.
        (repo_root / "a.txt").write_text("base\nchange\n", encoding="utf-8")

        # Run from tmp_path to exercise the real .cache/build layout.
        old_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            env = {"repositories": [(str(repo_root), "root")]}
            assert self.project_diff(env, {}, "projA", keep_diff_dir=False) is True
        finally:
            os.chdir(old_cwd)

        build_root = tmp_path / ".cache" / "build" / "projA"
        ts_dirs = [p for p in build_root.iterdir() if p.is_dir()]
        assert len(ts_dirs) == 1
        ts_dir = ts_dirs[0]

        archive = next(ts_dir.glob("diff_projA_*.tar.gz"))
        assert archive.is_file()
        assert not (ts_dir / "diff").exists()

        with tarfile.open(str(archive), "r:gz") as tar:
            names = set(tar.getnames())
        assert "diff/after/a.txt" in names
        assert "diff/before/a.txt" in names
        assert "diff/patch/changes_worktree.patch" in names
        # Single repo should not create a repo-name subdir.
        assert "diff/after/root/a.txt" not in names

    def test_project_diff_multi_repo_archive_structure_real_git(self, tmp_path):
        """BUILD-002: Multi-repo diff archive groups files under repo subdirs."""
        repo1 = tmp_path / "repo1"
        repo2 = tmp_path / "repo2"
        repo1.mkdir(parents=True, exist_ok=True)
        repo2.mkdir(parents=True, exist_ok=True)

        def _init_repo(repo_root, fname: str, content: str) -> None:
            subprocess.run(
                ["git", "init"], cwd=str(repo_root), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=str(repo_root),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=str(repo_root),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            (repo_root / fname).write_text(content, encoding="utf-8")
            subprocess.run(
                ["git", "add", fname],
                cwd=str(repo_root),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "commit", "-m", "base"],
                cwd=str(repo_root),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        _init_repo(repo1, "a.txt", "r1\n")
        _init_repo(repo2, "b.txt", "r2\n")

        # Create worktree changes.
        (repo1 / "a.txt").write_text("r1\nchange\n", encoding="utf-8")
        (repo2 / "b.txt").write_text("r2\nchange\n", encoding="utf-8")

        old_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            env = {"repositories": [(str(repo1), "repo1"), (str(repo2), "repo2")]}
            assert self.project_diff(env, {}, "projA", keep_diff_dir=False) is True
        finally:
            os.chdir(old_cwd)

        build_root = tmp_path / ".cache" / "build" / "projA"
        ts_dirs = [p for p in build_root.iterdir() if p.is_dir()]
        assert len(ts_dirs) == 1
        ts_dir = ts_dirs[0]

        archive = next(ts_dir.glob("diff_projA_*.tar.gz"))
        assert archive.is_file()

        with tarfile.open(str(archive), "r:gz") as tar:
            names = set(tar.getnames())
        assert "diff/after/repo1/a.txt" in names
        assert "diff/before/repo1/a.txt" in names
        assert "diff/patch/repo1/changes_worktree.patch" in names
        assert "diff/after/repo2/b.txt" in names
        assert "diff/before/repo2/b.txt" in names
        assert "diff/patch/repo2/changes_worktree.patch" in names

    def test_project_diff_clean_repo_has_no_patch_files_real_git(self, tmp_path):
        """BUILD-003: No changes => no patch files in archive."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir(parents=True, exist_ok=True)

        def _git(*args: str) -> None:
            subprocess.run(
                ["git", *args],
                cwd=str(repo_root),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        _git("init")
        _git("config", "user.email", "test@example.com")
        _git("config", "user.name", "Test User")
        (repo_root / "a.txt").write_text("base\n", encoding="utf-8")
        _git("add", "a.txt")
        _git("commit", "-m", "base")

        old_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            env = {"repositories": [(str(repo_root), "root")]}
            assert self.project_diff(env, {}, "projA", keep_diff_dir=False) is True
        finally:
            os.chdir(old_cwd)

        build_root = tmp_path / ".cache" / "build" / "projA"
        ts_dir = next(p for p in build_root.iterdir() if p.is_dir())
        archive = next(ts_dir.glob("diff_projA_*.tar.gz"))

        with tarfile.open(str(archive), "r:gz") as tar:
            names = set(tar.getnames())

        assert "diff/patch/changes_worktree.patch" not in names
        assert "diff/patch/changes_staged.patch" not in names

    def test_project_diff_keep_diff_dir_preserves_output_real_git(self, tmp_path):
        """BUILD-004: --keep-diff-dir preserves diff directory after archiving."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir(parents=True, exist_ok=True)

        def _git(*args: str) -> None:
            subprocess.run(
                ["git", *args],
                cwd=str(repo_root),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        _git("init")
        _git("config", "user.email", "test@example.com")
        _git("config", "user.name", "Test User")
        (repo_root / "a.txt").write_text("base\n", encoding="utf-8")
        _git("add", "a.txt")
        _git("commit", "-m", "base")
        (repo_root / "a.txt").write_text("base\nchange\n", encoding="utf-8")

        old_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            env = {"repositories": [(str(repo_root), "root")]}
            assert self.project_diff(env, {}, "projA", keep_diff_dir=True) is True
        finally:
            os.chdir(old_cwd)

        build_root = tmp_path / ".cache" / "build" / "projA"
        ts_dir = next(p for p in build_root.iterdir() if p.is_dir())
        archive = next(ts_dir.glob("diff_projA_*.tar.gz"))
        assert archive.is_file()
        assert (ts_dir / "diff").is_dir()
        assert (ts_dir / "diff" / "after").is_dir()
        assert (ts_dir / "diff" / "before").is_dir()
        assert (ts_dir / "diff" / "patch").is_dir()
        assert (ts_dir / "diff" / "commit").is_dir()


class TestProjectPreBuild:
    """Test cases for project_pre_build function."""

    def setup_method(self):
        """
        Prepare the test environment for each test case.
        - Adds the project root to sys.path if not already present, ensuring modules can be imported correctly.
        - Imports the function/class from src.plugins.project_builder and assigns it to self.project_pre_build for use in test cases.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
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
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
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

    @patch("src.plugins.project_builder.subprocess.run")
    def test_project_do_build_runs_configured_command(self, mock_run):
        """When PROJECT_BUILD_CMD is set, project_do_build should execute it."""
        mock_run.return_value = MagicMock(returncode=0)
        env = {"root_path": "/tmp/root"}
        projects_info = {"p": {"config": {"PROJECT_BUILD_CMD": "echo hello", "PROJECT_BUILD_CWD": "work"}}}

        result = self.project_do_build(env, projects_info, "p")
        assert result is True
        mock_run.assert_called_once()
        called_args, called_kwargs = mock_run.call_args
        assert called_args[0] == ["echo", "hello"]
        assert called_kwargs["cwd"] == "/tmp/root/work"

    @patch("src.plugins.project_builder.subprocess.run")
    def test_project_do_build_command_failure_returns_false(self, mock_run):
        """Non-zero return code should fail build stage."""
        mock_run.return_value = MagicMock(returncode=2)
        env = {"root_path": "/tmp/root"}
        projects_info = {"p": {"config": {"PROJECT_BUILD_CMD": "false"}}}

        assert self.project_do_build(env, projects_info, "p") is False

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
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
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

    @patch("src.plugins.project_builder.subprocess.run")
    def test_project_post_build_runs_configured_command(self, mock_run):
        """When PROJECT_POST_BUILD_CMD is set, project_post_build should execute it."""
        mock_run.return_value = MagicMock(returncode=0)
        env = {"root_path": "/tmp/root"}
        projects_info = {"p": {"config": {"PROJECT_POST_BUILD_CMD": "echo done", "PROJECT_POST_BUILD_CWD": "work"}}}

        result = self.project_post_build(env, projects_info, "p")
        assert result is True
        mock_run.assert_called_once()
        called_args, called_kwargs = mock_run.call_args
        assert called_args[0] == ["echo", "done"]
        assert called_kwargs["cwd"] == "/tmp/root/work"

    @patch("src.plugins.project_builder.subprocess.run")
    def test_project_post_build_command_failure_returns_false(self, mock_run):
        """Non-zero return code should fail post-build stage."""
        mock_run.return_value = MagicMock(returncode=1)
        env = {"root_path": "/tmp/root"}
        projects_info = {"p": {"config": {"PROJECT_POST_BUILD_CMD": "false"}}}

        assert self.project_post_build(env, projects_info, "p") is False

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
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
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

    @patch("src.plugins.project_builder.execute_hooks_with_fallback")
    @patch("src.plugins.project_builder.project_pre_build")
    def test_project_build_validation_hook_failure_aborts(self, mock_pre_build, mock_exec_hooks):
        """BUILD-005: Validation hook failure aborts build."""
        from src.hooks import HookType
        from src.hooks import registry as hooks_registry

        old_hooks = hooks_registry._platform_hooks
        try:
            hooks_registry._platform_hooks = {"linux": {HookType.VALIDATION.value: [lambda _ctx: False]}}
            mock_exec_hooks.return_value = False
            mock_pre_build.return_value = True

            env = {}
            projects_info = {"p": {"config": {"PROJECT_PLATFORM": "linux"}}}
            assert self.project_build(env, projects_info, "p") is False
            mock_pre_build.assert_not_called()
        finally:
            hooks_registry._platform_hooks = old_hooks

    @patch("src.plugins.project_builder.execute_hooks_with_fallback")
    @patch("src.plugins.project_builder.project_pre_build")
    @patch("src.plugins.project_builder.project_do_build")
    @patch("src.plugins.project_builder.project_post_build")
    def test_project_build_pre_build_hook_failure_aborts(
        self, mock_post_build, mock_do_build, mock_pre_build, mock_exec_hooks
    ):
        """BUILD-006: Pre-build hook failure aborts."""
        from src.hooks import HookType
        from src.hooks import registry as hooks_registry

        old_hooks = hooks_registry._platform_hooks
        try:
            hooks_registry._platform_hooks = {"linux": {HookType.PRE_BUILD.value: [lambda _ctx: False]}}
            mock_exec_hooks.return_value = False
            mock_pre_build.return_value = True
            mock_do_build.return_value = True
            mock_post_build.return_value = True

            env = {}
            projects_info = {"p": {"config": {"PROJECT_PLATFORM": "linux"}}}
            assert self.project_build(env, projects_info, "p") is False
            mock_pre_build.assert_called_once()
            mock_do_build.assert_not_called()
            mock_post_build.assert_not_called()
        finally:
            hooks_registry._platform_hooks = old_hooks

    @patch("src.plugins.project_builder.execute_hooks_with_fallback")
    @patch("src.plugins.project_builder.project_pre_build")
    @patch("src.plugins.project_builder.project_do_build")
    @patch("src.plugins.project_builder.project_post_build")
    def test_project_build_build_hook_failure_aborts(
        self, mock_post_build, mock_do_build, mock_pre_build, mock_exec_hooks
    ):
        """BUILD-006: Build hook failure aborts."""
        from src.hooks import HookType
        from src.hooks import registry as hooks_registry

        old_hooks = hooks_registry._platform_hooks
        try:
            hooks_registry._platform_hooks = {"linux": {HookType.BUILD.value: [lambda _ctx: False]}}
            mock_exec_hooks.return_value = False
            mock_pre_build.return_value = True
            mock_do_build.return_value = True
            mock_post_build.return_value = True

            env = {}
            projects_info = {"p": {"config": {"PROJECT_PLATFORM": "linux"}}}
            assert self.project_build(env, projects_info, "p") is False
            mock_pre_build.assert_called_once()
            mock_do_build.assert_not_called()
            mock_post_build.assert_not_called()
        finally:
            hooks_registry._platform_hooks = old_hooks

    @patch("src.plugins.project_builder.execute_hooks_with_fallback")
    @patch("src.plugins.project_builder.project_pre_build")
    @patch("src.plugins.project_builder.project_do_build")
    @patch("src.plugins.project_builder.project_post_build")
    def test_project_build_post_build_hook_failure_aborts(
        self, mock_post_build, mock_do_build, mock_pre_build, mock_exec_hooks
    ):
        """BUILD-006: Post-build hook failure aborts."""
        from src.hooks import HookType
        from src.hooks import registry as hooks_registry

        old_hooks = hooks_registry._platform_hooks
        try:
            hooks_registry._platform_hooks = {"linux": {HookType.POST_BUILD.value: [lambda _ctx: False]}}
            mock_exec_hooks.return_value = False
            mock_pre_build.return_value = True
            mock_do_build.return_value = True
            mock_post_build.return_value = True

            env = {}
            projects_info = {"p": {"config": {"PROJECT_PLATFORM": "linux"}}}
            assert self.project_build(env, projects_info, "p") is False
            mock_pre_build.assert_called_once()
            mock_do_build.assert_called_once()
            mock_post_build.assert_not_called()
        finally:
            hooks_registry._platform_hooks = old_hooks

    @patch("src.plugins.project_builder.execute_hooks_with_fallback")
    @patch("src.plugins.project_builder.project_pre_build")
    @patch("src.plugins.project_builder.project_do_build")
    @patch("src.plugins.project_builder.project_post_build")
    def test_project_build_no_platform_skips_hooks(
        self, mock_post_build, mock_do_build, mock_pre_build, mock_exec_hooks
    ):
        """BUILD-007: No platform skips hooks."""
        from src.hooks import registry as hooks_registry

        old_hooks = hooks_registry._platform_hooks
        try:
            # Hooks exist for some platform, but project has no platform so they must be skipped.
            hooks_registry._platform_hooks = {"linux": {"validation": [lambda _ctx: True]}}
            mock_exec_hooks.side_effect = AssertionError("execute_hooks_with_fallback should not be called")
            mock_pre_build.return_value = True
            mock_do_build.return_value = True
            mock_post_build.return_value = True

            env = {}
            projects_info = {"p": {"config": {}}}
            assert self.project_build(env, projects_info, "p") is True
        finally:
            hooks_registry._platform_hooks = old_hooks
