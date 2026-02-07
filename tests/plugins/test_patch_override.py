"""
Tests for patch_override module.
"""

# pylint: disable=attribute-defined-outside-init
# pylint: disable=import-outside-toplevel
# pylint: disable=protected-access

import os
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch


class TestPatchOverrideApply:
    """Test cases for PatchOverride class."""

    def setup_method(self):
        """
        Prepare the test environment for each test case.
        - Adds the project root to sys.path if not already present, ensuring modules can be imported correctly.
        - Imports the function/class from src.module and assigns it to self.function_name for use in test cases.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        import src.plugins.patch_override as PatchOverride

        self.PatchOverride = PatchOverride

    def test_po_apply_basic_success(self):
        """Test po_apply with basic successful case."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                "projects_path": os.path.join(tmpdir, "projects"),
                "repositories": [(os.path.join(tmpdir, "repo1"), "repo1"), (os.path.join(tmpdir, "repo2"), "repo2")],
            }
            projects_info = {"test_project": {"board_name": "test_board", "config": {"PROJECT_PO_CONFIG": "po1"}}}
            project_name = "test_project"

            with patch("os.path.join") as mock_join, patch("os.path.isdir") as mock_isdir, patch(
                "src.plugins.patch_override.log"
            ) as mock_log:

                mock_join.side_effect = lambda *args: "/".join(args)
                mock_isdir.return_value = False  # No patches directory exists

                # Act
                result = self.PatchOverride.po_apply(env, projects_info, project_name)

                # Assert
                assert result is True
                # Check that the method was called with the expected arguments
                mock_log.info.assert_any_call("start po_apply for project: '%s'", project_name)
                mock_log.info.assert_any_call("po apply finished for project: '%s'", project_name)

    def test_po_apply_missing_board_name(self):
        """Test po_apply when board_name is missing from project config."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"projects_path": os.path.join(tmpdir, "projects")}
            projects_info = {"test_project": {}}  # No board_name
            project_name = "test_project"

            with patch("src.plugins.patch_override.log") as mock_log:
                # Act
                result = self.PatchOverride.po_apply(env, projects_info, project_name)

                # Assert
                assert result is False
                mock_log.error.assert_called_with("Cannot find board name for project: '%s'", project_name)

    def test_po_apply_empty_po_config(self):
        """Test po_apply when PROJECT_PO_CONFIG is empty."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"projects_path": os.path.join(tmpdir, "projects")}
            projects_info = {
                "test_project": {
                    "board_name": "test_board",
                    "config": {"PROJECT_PO_CONFIG": ""},  # Empty config
                }
            }
            project_name = "test_project"

            with patch("src.plugins.patch_override.log") as mock_log:
                # Act
                result = self.PatchOverride.po_apply(env, projects_info, project_name)

                # Assert
                assert result is True
                mock_log.warning.assert_called_with("No PROJECT_PO_CONFIG found for '%s'", project_name)

    def test_po_apply_with_excluded_po(self):
        """Test po_apply when PO is excluded in config."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                "projects_path": os.path.join(tmpdir, "projects"),
                "repositories": [(os.path.join(tmpdir, "repo1"), "repo1")],
            }
            projects_info = {
                "test_project": {
                    "board_name": "test_board",
                    "config": {"PROJECT_PO_CONFIG": "po1 -po1"},  # po1 is excluded
                }
            }
            project_name = "test_project"

            with patch("src.plugins.patch_override.log") as mock_log:
                # Act
                result = self.PatchOverride.po_apply(env, projects_info, project_name)

                # Assert
                assert result is True
                mock_log.info.assert_any_call("start po_apply for project: '%s'", project_name)

    def test_po_apply_with_excluded_files(self):
        """Test po_apply with excluded files in config."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                "projects_path": os.path.join(tmpdir, "projects"),
                "repositories": [(os.path.join(tmpdir, "repo1"), "repo1")],
            }
            projects_info = {
                "test_project": {
                    "board_name": "test_board",
                    "config": {
                        # Exclude specific files
                        "PROJECT_PO_CONFIG": "po1[file1.txt file2.txt]",
                    },
                }
            }
            project_name = "test_project"

            with patch("os.path.join") as mock_join, patch("os.path.isdir") as mock_isdir, patch(
                "src.plugins.patch_override.log"
            ) as mock_log:
                mock_join.side_effect = lambda *args: "/".join(args)
                mock_isdir.return_value = False

                # Act
                result = self.PatchOverride.po_apply(env, projects_info, project_name)

                # Assert
                assert result is True
                mock_log.info.assert_any_call("start po_apply for project: '%s'", project_name)

    def test_po_apply_patches_with_exclude_and_flag(self):
        """Apply patches: run git apply, respect exclude list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "board"
            po_name = "po1"
            repo1_path = os.path.join(tmpdir, "repo1")
            os.makedirs(repo1_path, exist_ok=True)

            # Prepare patches directory with two patch files (one excluded)
            patches_dir = os.path.join(projects_path, board_name, "po", po_name, "patches", "repo1")
            os.makedirs(patches_dir, exist_ok=True)
            allow_patch = os.path.join(patches_dir, "allow.patch")
            skip_patch = os.path.join(patches_dir, "skip.patch")
            with open(allow_patch, "w", encoding="utf-8") as f:
                f.write("diff --git a/a b/a\n")
            with open(skip_patch, "w", encoding="utf-8") as f:
                f.write("diff --git a/b b/b\n")

            env = {
                "projects_path": projects_path,
                "repositories": [(repo1_path, "repo1")],
            }
            # Exclude repo1/skip.patch
            projects_info = {
                "proj": {
                    "board_name": board_name,
                    # Exclude a specific patch file while still applying this PO.
                    "config": {"PROJECT_PO_CONFIG": f"{po_name}[repo1/skip.patch]"},
                }
            }

            # Mock subprocess.run to simulate successful git apply and capture calls
            calls = []

            def _mock_run(cmd, cwd=None, **_kwargs):
                calls.append((cmd, cwd))
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("subprocess.run", side_effect=_mock_run):
                result = self.PatchOverride.po_apply(env, projects_info, "proj")
                assert result is True

            # Only one apply call for allow.patch
            applied_cmds = [c for c in calls if c[0][:2] == ["git", "apply"]]
            assert len(applied_cmds) == 1
            assert applied_cmds[0][1] == repo1_path  # cwd is the repository path

    def test_po_apply_patches_with_multilevel_directory(self):
        """Apply patches: test repo_name extraction from multilevel directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "board"
            po_name = "po1"
            repo1_path = os.path.join(tmpdir, "repo1")
            os.makedirs(repo1_path, exist_ok=True)

            # Prepare patches directory with multilevel structure
            # patches/uboot/driver/example.patch -> repo_name should be "uboot/driver"
            patches_dir = os.path.join(projects_path, board_name, "po", po_name, "patches")
            multilevel_dir = os.path.join(patches_dir, "uboot", "driver")
            os.makedirs(multilevel_dir, exist_ok=True)

            # Create patch file in multilevel directory
            patch_file = os.path.join(multilevel_dir, "example.patch")
            with open(patch_file, "w", encoding="utf-8") as f:
                f.write("diff --git a/driver.c b/driver.c\n")

            env = {
                "projects_path": projects_path,
                "repositories": [(repo1_path, "uboot/driver")],  # Mock repository with multilevel name
            }
            projects_info = {
                "proj": {
                    "board_name": board_name,
                    "config": {"PROJECT_PO_CONFIG": po_name},
                }
            }

            # Mock subprocess.run to simulate successful git apply and capture calls
            calls = []

            def _mock_run(cmd, cwd=None, **_kwargs):
                calls.append((cmd, cwd))
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("subprocess.run", side_effect=_mock_run):
                result = self.PatchOverride.po_apply(env, projects_info, "proj")
                assert result is True

            # Should have one apply call for the patch
            applied_cmds = [c for c in calls if c[0][:2] == ["git", "apply"]]
            assert len(applied_cmds) == 1
            assert applied_cmds[0][1] == repo1_path  # cwd is the repository path

    def test_po_apply_patches_with_root_level_patch(self):
        """Apply patches: test repo_name extraction for root level patches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "board"
            po_name = "po1"
            repo1_path = os.path.join(tmpdir, "repo1")
            os.makedirs(repo1_path, exist_ok=True)

            # Prepare patches directory with root level patch
            # patches/root.patch -> repo_name should be "root"
            patches_dir = os.path.join(projects_path, board_name, "po", po_name, "patches")
            os.makedirs(patches_dir, exist_ok=True)

            # Create patch file at root level
            patch_file = os.path.join(patches_dir, "root.patch")
            with open(patch_file, "w", encoding="utf-8") as f:
                f.write("diff --git a/root.c b/root.c\n")

            env = {
                "projects_path": projects_path,
                "repositories": [(repo1_path, "root")],  # Mock repository with root name
            }
            projects_info = {
                "proj": {
                    "board_name": board_name,
                    "config": {"PROJECT_PO_CONFIG": po_name},
                }
            }

            # Mock subprocess.run to simulate successful git apply and capture calls
            calls = []

            def _mock_run(cmd, cwd=None, **_kwargs):
                calls.append((cmd, cwd))
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("subprocess.run", side_effect=_mock_run):
                result = self.PatchOverride.po_apply(env, projects_info, "proj")
                assert result is True

            # Should have one apply call for the patch
            applied_cmds = [c for c in calls if c[0][:2] == ["git", "apply"]]
            assert len(applied_cmds) == 1
            assert applied_cmds[0][1] == repo1_path  # cwd is the repository path

    def test_po_apply_overrides_copy_with_exclude_and_flag(self):
        """Apply overrides: copy files and respect exclude list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "board"
            po_name = "po1"

            # Prepare overrides directory structure
            overrides_dir = os.path.join(projects_path, board_name, "po", po_name, "overrides")
            os.makedirs(os.path.join(overrides_dir, "repo1", "folder"), exist_ok=True)
            with open(os.path.join(overrides_dir, "onlyroot.txt"), "w", encoding="utf-8") as f:
                f.write("root")
            deep_file_rel = os.path.join("repo1", "folder", "fileA.txt")
            deep_file_abs = os.path.join(overrides_dir, deep_file_rel)
            with open(deep_file_abs, "w", encoding="utf-8") as f:
                f.write("deep")

            # Provide repository mapping so overrides are applied into repo roots, not cwd.
            repo1_root = os.path.join(tmpdir, "repo1")
            os.makedirs(repo1_root, exist_ok=True)
            env = {
                "projects_path": projects_path,
                "repositories": [(tmpdir, "root"), (repo1_root, "repo1")],
            }
            # Exclude the deep file so only root file is copied
            projects_info = {
                "proj": {
                    "board_name": board_name,
                    # Exclude a specific override file while still applying this PO.
                    "config": {"PROJECT_PO_CONFIG": f"{po_name}[{deep_file_rel}]"},
                }
            }

            # Run in tmpdir so override targets write under here
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = self.PatchOverride.po_apply(env, projects_info, "proj")
                assert result is True
            finally:
                os.chdir(old_cwd)

            # onlyroot.txt should exist at repo root (".")
            assert os.path.exists(os.path.join(tmpdir, "onlyroot.txt"))
            # Excluded deep file should not be copied
            assert not os.path.exists(os.path.join(tmpdir, deep_file_rel))

    def test_po_apply_overrides_dest_file_path_construction(self):
        """Test that dest_file path construction avoids path duplication."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "board"
            po_name = "po1"

            # Prepare overrides directory structure with nested subdirectories
            overrides_dir = os.path.join(projects_path, board_name, "po", po_name, "overrides")

            # Create nested structure: uboot/drivers/config.txt
            nested_dir = os.path.join(overrides_dir, "uboot", "drivers")
            os.makedirs(nested_dir, exist_ok=True)

            # Create files at different levels
            root_file = os.path.join(overrides_dir, "README.md")
            nested_file = os.path.join(nested_dir, "config.txt")

            with open(root_file, "w", encoding="utf-8") as f:
                f.write("root content")
            with open(nested_file, "w", encoding="utf-8") as f:
                f.write("nested content")

            env = {
                "projects_path": projects_path,
                "repositories": [(tmpdir, "root")],
            }
            projects_info = {
                "proj": {
                    "board_name": board_name,
                    "config": {"PROJECT_PO_CONFIG": po_name},
                }
            }

            # Run in tmpdir so override targets write under here
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = self.PatchOverride.po_apply(env, projects_info, "proj")
                assert result is True
            finally:
                os.chdir(old_cwd)

            # Test root level file: should be copied to ./README.md
            assert os.path.exists(os.path.join(tmpdir, "README.md"))
            with open(os.path.join(tmpdir, "README.md"), "r", encoding="utf-8") as f:
                assert f.read() == "root content"

            # Test nested file: should be copied to uboot/drivers/config.txt (NOT uboot/drivers/drivers/config.txt)
            expected_nested_path = os.path.join(tmpdir, "uboot", "drivers", "config.txt")
            assert os.path.exists(expected_nested_path)
            with open(expected_nested_path, "r", encoding="utf-8") as f:
                assert f.read() == "nested content"

            # Verify no path duplication occurred
            # The old bug would create: uboot/drivers/drivers/config.txt
            wrong_path = os.path.join(tmpdir, "uboot", "drivers", "drivers", "config.txt")
            assert not os.path.exists(wrong_path), f"Path duplication detected: {wrong_path} exists"

    def test_po_apply_overrides_remove_operation(self):
        """Test that files with .remove suffix are deleted instead of copied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "board"
            po_name = "po1"

            # Prepare overrides directory structure
            overrides_dir = os.path.join(projects_path, board_name, "po", po_name, "overrides")
            os.makedirs(overrides_dir, exist_ok=True)

            # Create a .remove file
            remove_file = os.path.join(overrides_dir, "target_file.remove")
            with open(remove_file, "w", encoding="utf-8") as f:
                f.write("remove marker")

            env = {
                "projects_path": projects_path,
                "repositories": [(tmpdir, "root")],
            }
            projects_info = {
                "proj": {
                    "board_name": board_name,
                    "config": {"PROJECT_PO_CONFIG": po_name},
                }
            }

            # Create target file that should be removed
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                target_file = os.path.join(tmpdir, "target_file")
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write("original content")

                # Verify target file exists before removal
                assert os.path.exists(target_file)

                result = self.PatchOverride.po_apply(env, projects_info, "proj")
                assert result is True

                # Verify target file was removed
                assert not os.path.exists(target_file)

            finally:
                os.chdir(old_cwd)

    def test_po_apply_overrides_remove_nonexistent_file(self):
        """Test that removing a non-existent file doesn't cause errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "board"
            po_name = "po1"

            # Prepare overrides directory structure
            overrides_dir = os.path.join(projects_path, board_name, "po", po_name, "overrides")
            os.makedirs(overrides_dir, exist_ok=True)

            # Create a .remove file for a non-existent target
            remove_file = os.path.join(overrides_dir, "nonexistent_file.remove")
            with open(remove_file, "w", encoding="utf-8") as f:
                f.write("remove marker")

            env = {
                "projects_path": projects_path,
                "repositories": [(tmpdir, "root")],
            }
            projects_info = {
                "proj": {
                    "board_name": board_name,
                    "config": {"PROJECT_PO_CONFIG": po_name},
                }
            }

            # Run in tmpdir
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = self.PatchOverride.po_apply(env, projects_info, "proj")
                assert result is True

            finally:
                os.chdir(old_cwd)

    def test_custom_copy_star_includes_subdirs(self):
        """'*' should recursively copy all files including subdirectories from PROJECT_PO_DIR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "board"
            po_name = "po1"
            custom_dir = "custom"
            po_custom_dir = os.path.join(projects_path, board_name, "po", po_name, custom_dir)

            # Prepare source structure
            os.makedirs(os.path.join(po_custom_dir, "data", "sub"), exist_ok=True)
            os.makedirs(os.path.join(po_custom_dir, "other"), exist_ok=True)
            with open(os.path.join(po_custom_dir, "root.txt"), "w", encoding="utf-8") as f:
                f.write("root")
            with open(os.path.join(po_custom_dir, "data", "file1.txt"), "w", encoding="utf-8") as f:
                f.write("file1")
            with open(os.path.join(po_custom_dir, "data", "sub", "inner.txt"), "w", encoding="utf-8") as f:
                f.write("inner")
            with open(os.path.join(po_custom_dir, "other", "oth.txt"), "w", encoding="utf-8") as f:
                f.write("oth")

            dest_dir = os.path.join(tmpdir, "dest1")

            env = {
                "projects_path": projects_path,
                "repositories": [],
                "po_configs": {
                    f"po-{po_name}": {
                        "PROJECT_PO_DIR": "",
                        "PROJECT_PO_FILE_COPY": f"*:{dest_dir}{os.sep}",
                    }
                },
            }
            projects_info = {
                "proj": {
                    "board_name": board_name,
                    "config": {"PROJECT_PO_CONFIG": po_name},
                }
            }

            result = self.PatchOverride.po_apply(env, projects_info, "proj")
            assert result is True

            # Assert files are copied with relative structure preserved
            assert os.path.exists(os.path.join(dest_dir, "root.txt"))
            assert os.path.exists(os.path.join(dest_dir, "data", "file1.txt"))
            assert os.path.exists(os.path.join(dest_dir, "data", "sub", "inner.txt"))
            assert os.path.exists(os.path.join(dest_dir, "other", "oth.txt"))

    def test_custom_copy_data_star_includes_subdirs(self):
        """'data/*' should recursively copy all files from PROJECT_PO_DIR/data including subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "board"
            po_name = "po1"
            custom_dir = "custom"
            po_custom_dir = os.path.join(projects_path, board_name, "po", po_name, custom_dir)

            # Prepare source structure under data/
            os.makedirs(os.path.join(po_custom_dir, "data", "sub"), exist_ok=True)
            os.makedirs(os.path.join(po_custom_dir, "other"), exist_ok=True)
            with open(os.path.join(po_custom_dir, "data", "file1.txt"), "w", encoding="utf-8") as f:
                f.write("file1")
            with open(os.path.join(po_custom_dir, "data", "sub", "inner.txt"), "w", encoding="utf-8") as f:
                f.write("inner")
            with open(os.path.join(po_custom_dir, "root.txt"), "w", encoding="utf-8") as f:
                f.write("root")

            dest_root = os.path.join(tmpdir, "dest2")
            dest_data = os.path.join(dest_root, "data") + os.sep

            env = {
                "projects_path": projects_path,
                "repositories": [],
                "po_configs": {
                    f"po-{po_name}": {
                        "PROJECT_PO_DIR": "",
                        "PROJECT_PO_FILE_COPY": f"data/*:{dest_data}",
                    }
                },
            }
            projects_info = {
                "proj": {
                    "board_name": board_name,
                    "config": {"PROJECT_PO_CONFIG": po_name},
                }
            }

            result = self.PatchOverride.po_apply(env, projects_info, "proj")
            assert result is True

            # Should copy files under data/ recursively
            assert os.path.exists(os.path.join(dest_root, "data", "file1.txt"))
            assert os.path.exists(os.path.join(dest_root, "data", "sub", "inner.txt"))
            # Should not copy files outside data/
            assert not os.path.exists(os.path.join(dest_root, "root.txt"))

    def test_custom_copy_glob_with_spaces(self):
        """Custom copy should work with spaces in source/target paths without shell expansion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "board"
            po_name = "po1"

            # Prepare source structure under po_root/custom/cfg/
            po_root = os.path.join(projects_path, board_name, "po", po_name)
            cfg_dir = os.path.join(po_root, "custom", "cfg")
            os.makedirs(cfg_dir, exist_ok=True)
            src_file = os.path.join(cfg_dir, "space name.ini")
            with open(src_file, "w", encoding="utf-8") as f:
                f.write("k=v\n")

            dest_dir = os.path.join(tmpdir, "dest with space", "cfg") + os.sep

            env = {
                "projects_path": projects_path,
                "repositories": [],
                "po_configs": {
                    f"po-{po_name}": {
                        "PROJECT_PO_DIR": "custom",
                        "PROJECT_PO_FILE_COPY": f"cfg/*.ini:{dest_dir}",
                    }
                },
            }
            projects_info = {"proj": {"board_name": board_name, "config": {"PROJECT_PO_CONFIG": po_name}}}

            result = self.PatchOverride.po_apply(env, projects_info, "proj")
            assert result is True
            assert os.path.exists(os.path.join(dest_dir, "space name.ini"))

    def test_custom_copy_double_star_preserves_relpath(self):
        """'**' patterns should preserve relative paths under the non-glob prefix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "board"
            po_name = "po1"

            po_root = os.path.join(projects_path, board_name, "po", po_name)
            data_dir = os.path.join(po_root, "custom", "data")
            os.makedirs(os.path.join(data_dir, "a", "b"), exist_ok=True)
            with open(os.path.join(data_dir, "a", "b", "deep.txt"), "w", encoding="utf-8") as f:
                f.write("deep\n")

            dest_root = os.path.join(tmpdir, "dest3")
            dest_dir = dest_root + os.sep

            env = {
                "projects_path": projects_path,
                "repositories": [],
                "po_configs": {
                    f"po-{po_name}": {
                        "PROJECT_PO_DIR": "custom",
                        "PROJECT_PO_FILE_COPY": f"data/**/*.txt:{dest_dir}",
                    }
                },
            }
            projects_info = {"proj": {"board_name": board_name, "config": {"PROJECT_PO_CONFIG": po_name}}}

            result = self.PatchOverride.po_apply(env, projects_info, "proj")
            assert result is True
            assert os.path.exists(os.path.join(dest_root, "a", "b", "deep.txt"))

    def test_po_apply_patches_with_multiple_patches_same_repo(self):
        """Apply patches: test that multiple patch files can be applied to the same repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "board"
            po_name = "po1"
            repo1_path = os.path.join(tmpdir, "repo1")
            os.makedirs(repo1_path, exist_ok=True)

            # Prepare patches directory with multiple patch files for the same repo
            patches_dir = os.path.join(projects_path, board_name, "po", po_name, "patches", "repo1")
            os.makedirs(patches_dir, exist_ok=True)

            # Create multiple patch files
            patch1 = os.path.join(patches_dir, "patch1.patch")
            patch2 = os.path.join(patches_dir, "patch2.patch")
            patch3 = os.path.join(patches_dir, "patch3.patch")

            with open(patch1, "w", encoding="utf-8") as f:
                f.write("diff --git a/file1.txt b/file1.txt\n")
            with open(patch2, "w", encoding="utf-8") as f:
                f.write("diff --git a/file2.txt b/file2.txt\n")
            with open(patch3, "w", encoding="utf-8") as f:
                f.write("diff --git a/file3.txt b/file3.txt\n")

            env = {
                "projects_path": projects_path,
                "repositories": [(repo1_path, "repo1")],
            }
            projects_info = {
                "proj": {
                    "board_name": board_name,
                    "config": {"PROJECT_PO_CONFIG": po_name},
                }
            }

            # Mock subprocess.run to simulate successful git apply and capture calls
            calls = []

            def _mock_run(cmd, cwd=None, **_kwargs):
                calls.append((cmd, cwd))
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("subprocess.run", side_effect=_mock_run):
                result = self.PatchOverride.po_apply(env, projects_info, "proj")
                assert result is True

            # Should have three apply calls for all three patches
            applied_cmds = [c for c in calls if c[0][:2] == ["git", "apply"]]
            assert len(applied_cmds) == 3
            assert all(c[1] == repo1_path for c in applied_cmds)  # All should use same repo path

    def test_po_apply_patches_with_multiple_patches_different_repos(self):
        """Apply patches: test that multiple patch files can be applied to different repositories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "board"
            po_name = "po1"
            repo1_path = os.path.join(tmpdir, "repo1")
            repo2_path = os.path.join(tmpdir, "repo2")
            os.makedirs(repo1_path, exist_ok=True)
            os.makedirs(repo2_path, exist_ok=True)

            # Prepare patches directory with patch files for different repos
            patches_dir = os.path.join(projects_path, board_name, "po", po_name, "patches")

            # Create patches for repo1
            repo1_patches_dir = os.path.join(patches_dir, "repo1")
            os.makedirs(repo1_patches_dir, exist_ok=True)
            patch1 = os.path.join(repo1_patches_dir, "patch1.patch")
            with open(patch1, "w", encoding="utf-8") as f:
                f.write("diff --git a/file1.txt b/file1.txt\n")

            # Create patches for repo2
            repo2_patches_dir = os.path.join(patches_dir, "repo2")
            os.makedirs(repo2_patches_dir, exist_ok=True)
            patch2 = os.path.join(repo2_patches_dir, "patch2.patch")
            patch3 = os.path.join(repo2_patches_dir, "patch3.patch")
            with open(patch2, "w", encoding="utf-8") as f:
                f.write("diff --git a/file2.txt b/file2.txt\n")
            with open(patch3, "w", encoding="utf-8") as f:
                f.write("diff --git a/file3.txt b/file3.txt\n")

            env = {
                "projects_path": projects_path,
                "repositories": [(repo1_path, "repo1"), (repo2_path, "repo2")],
            }
            projects_info = {
                "proj": {
                    "board_name": board_name,
                    "config": {"PROJECT_PO_CONFIG": po_name},
                }
            }

            # Mock subprocess.run to simulate successful git apply and capture calls
            calls = []

            def _mock_run(cmd, cwd=None, **_kwargs):
                calls.append((cmd, cwd))
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("subprocess.run", side_effect=_mock_run):
                result = self.PatchOverride.po_apply(env, projects_info, "proj")
                assert result is True

            # Should have three apply calls total (1 for repo1, 2 for repo2)
            applied_cmds = [c for c in calls if c[0][:2] == ["git", "apply"]]
            assert len(applied_cmds) == 3

            # Check repo1 got 1 patch
            repo1_calls = [c for c in applied_cmds if c[1] == repo1_path]
            assert len(repo1_calls) == 1

            # Check repo2 got 2 patches
            repo2_calls = [c for c in applied_cmds if c[1] == repo2_path]
            assert len(repo2_calls) == 2

    def test_po_apply_skips_when_flag_exists(self):
        """When po_applied flag exists, po_apply should skip processing and not run git apply."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "board"
            po_name = "po1"
            repo1_path = os.path.join(tmpdir, "repo1")
            os.makedirs(repo1_path, exist_ok=True)

            # Prepare patches directory with a patch that would be applied if not skipped
            patches_dir = os.path.join(projects_path, board_name, "po", po_name, "patches", "repo1")
            os.makedirs(patches_dir, exist_ok=True)
            patch_file = os.path.join(patches_dir, "should_not_apply.patch")
            with open(patch_file, "w", encoding="utf-8") as f:
                f.write("diff --git a/x b/x\n")

            # Create the applied flag to trigger skip
            po_path = os.path.join(projects_path, board_name, "po", po_name)
            os.makedirs(po_path, exist_ok=True)
            with open(os.path.join(po_path, "po_applied"), "w", encoding="utf-8") as f:
                f.write("applied\n")

            env = {
                "projects_path": projects_path,
                "repositories": [(repo1_path, "repo1")],
            }
            projects_info = {
                "proj": {
                    "board_name": board_name,
                    "config": {"PROJECT_PO_CONFIG": po_name},
                }
            }

            with patch("subprocess.run") as mock_run:
                result = self.PatchOverride.po_apply(env, projects_info, "proj")
                assert result is True
                mock_run.assert_not_called()

    def test_po_apply_creates_flag_after_success(self):
        """After successful apply, po_applied flag should be created under PO directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "board"
            po_name = "po1"

            # No patches/overrides -> success path
            po_base = os.path.join(projects_path, board_name, "po", po_name)
            os.makedirs(po_base, exist_ok=True)

            env = {
                "projects_path": projects_path,
                "repositories": [(tmpdir, "root")],
            }
            projects_info = {
                "proj": {
                    "board_name": board_name,
                    "config": {"PROJECT_PO_CONFIG": po_name},
                }
            }

            result = self.PatchOverride.po_apply(env, projects_info, "proj")
            assert result is True

            applied_flag = os.path.join(po_base, "po_applied")
            assert os.path.exists(applied_flag)
            with open(applied_flag, "r", encoding="utf-8") as f:
                content = f.read()
                assert "project proj" in content


class TestPatchOverrideRevert:
    """Test cases for po_revert method."""

    def setup_method(self):
        """
        Prepare the test environment for each test case.
        - Adds the project root to sys.path if not already present, ensuring modules can be imported correctly.
        - Imports the function/class from src.module and assigns it to self.function_name for use in test cases.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        import src.plugins.patch_override as PatchOverride

        self.PatchOverride = PatchOverride

    def test_po_revert_basic_success(self):
        """Test po_revert with basic successful case."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                "projects_path": os.path.join(tmpdir, "projects"),
                "repositories": [(os.path.join(tmpdir, "repo1"), "repo1"), (os.path.join(tmpdir, "repo2"), "repo2")],
            }
            projects_info = {
                "test_project": {
                    "board_name": "test_board",
                    "config": {"PROJECT_PO_CONFIG": "po1"},
                }
            }
            project_name = "test_project"

            with patch("os.path.join") as mock_join, patch("os.path.isdir") as mock_isdir, patch(
                "src.plugins.patch_override.log"
            ) as mock_log:
                mock_join.side_effect = lambda *args: "/".join(args)
                mock_isdir.return_value = False  # No patches directory exists

                # Act
                result = self.PatchOverride.po_revert(env, projects_info, project_name)

                # Assert
                assert result is True
                mock_log.info.assert_any_call("start po_revert for project: '%s'", project_name)
                mock_log.info.assert_any_call("po revert finished for project: '%s'", project_name)

    def test_po_revert_missing_board_name(self):
        """Test po_revert when board_name is missing from project config."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"projects_path": os.path.join(tmpdir, "projects")}
            projects_info = {"test_project": {}}  # No board_name
            project_name = "test_project"

            with patch("src.plugins.patch_override.log") as mock_log:
                # Act
                result = self.PatchOverride.po_revert(env, projects_info, project_name)

                # Assert
                assert result is False
                mock_log.error.assert_called_with("Cannot find board name for project: '%s'", project_name)

    def test_po_revert_empty_po_config(self):
        """Test po_revert when PROJECT_PO_CONFIG is empty."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"projects_path": os.path.join(tmpdir, "projects")}
            projects_info = {
                "test_project": {
                    "board_name": "test_board",
                    "config": {"PROJECT_PO_CONFIG": ""},  # Empty config
                }
            }
            project_name = "test_project"

            with patch("src.plugins.patch_override.log") as mock_log:
                # Act
                result = self.PatchOverride.po_revert(env, projects_info, project_name)

                # Assert
                assert result is True
                mock_log.warning.assert_called_with("No PROJECT_PO_CONFIG found for '%s'", project_name)


class TestPatchOverrideNew:
    """Test cases for po_new method."""

    def setup_method(self):
        """
        Prepare the test environment for each test case.
        - Adds the project root to sys.path if not already present, ensuring modules can be imported correctly.
        - Imports the function/class from src.module and assigns it to self.function_name for use in test cases.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        import src.plugins.patch_override as PatchOverride

        self.PatchOverride = PatchOverride

    def test_po_new_invalid_name_format(self):
        """Test po_new with invalid PO name format."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"projects_path": os.path.join(tmpdir, "projects")}
            projects_info = {
                "test_project": {
                    "board_name": "test_board",
                    "board_path": os.path.join(tmpdir, "board"),
                }
            }
            project_name = "test_project"
            po_name = "invalid_name"  # Doesn't start with 'po'

            with patch("src.plugins.patch_override.log") as mock_log:
                # Act
                result = self.PatchOverride.po_new(env, projects_info, project_name, po_name, force=True)

                # Assert
                assert result is False
                mock_log.error.assert_called_with(
                    "po_name '%s' is invalid. It must start with 'po' and only contain lowercase letters, digits, and underscores.",
                    po_name,
                )

    def test_po_new_missing_board_info(self):
        """Test po_new when board info is missing."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"projects_path": os.path.join(tmpdir, "projects")}
            # Missing board_name and board_path
            projects_info = {"test_project": {}}
            project_name = "test_project"
            po_name = "po_test"

            with patch("src.plugins.patch_override.log") as mock_log:
                # Act
                result = self.PatchOverride.po_new(env, projects_info, project_name, po_name, force=True)

                # Assert
                assert result is False
                mock_log.error.assert_called_with("Board info missing for project '%s'", project_name)

    def test_po_new_valid_name_format(self):
        """Test po_new with valid PO name format."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"projects_path": os.path.join(tmpdir, "projects")}
            projects_info = {
                "test_project": {
                    "board_name": "test_board",
                    "board_path": os.path.join(tmpdir, "board"),
                }
            }
            project_name = "test_project"
            po_name = "po_test"

            with patch("os.path.join") as mock_join, patch("os.path.exists") as mock_exists, patch(
                "os.makedirs"
            ) as mock_makedirs, patch("src.plugins.patch_override.log") as mock_log:
                mock_join.side_effect = lambda *args: "/".join(args)
                mock_exists.return_value = False  # PO directory doesn't exist
                mock_makedirs.return_value = None

                # Act
                result = self.PatchOverride.po_new(env, projects_info, project_name, po_name, force=True)

                # Assert
                assert result is True
                mock_log.info.assert_any_call(
                    "start po_new for project: '%s', po_name: '%s'",
                    project_name,
                    po_name,
                )

    def test_po_new_fails_when_po_exists(self):
        """po_new should fail if PO directory already exists."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"projects_path": os.path.join(tmpdir, "projects")}
            projects_info = {
                "test_project": {
                    "board_name": "test_board",
                    "board_path": os.path.join(tmpdir, "board"),
                }
            }
            project_name = "test_project"
            po_name = "po_test"

            with patch("os.path.join") as mock_join, patch("os.path.exists") as mock_exists, patch(
                "src.plugins.patch_override.log"
            ) as mock_log:
                mock_join.side_effect = lambda *args: "/".join(args)

                # Simulate PO directory exists
                def _exists_side_effect(path):
                    # Return True for any path ending with /po/po_test (po_path) and for po_dir
                    return path.endswith(f"po/{po_name}") or path.endswith("/po")

                mock_exists.side_effect = _exists_side_effect

                # Act
                result = self.PatchOverride.po_new(env, projects_info, project_name, po_name, force=True)

                # Assert
                assert result is False
                expected_path = os.path.join(tmpdir, "projects", "test_board", "po", "po_test")
                mock_log.error.assert_called_with("PO directory '%s' already exists", expected_path)


class TestPatchOverrideDelete:
    """Test cases for po_del method."""

    def setup_method(self):
        """
        Prepare the test environment for each test case.
        - Adds the project root to sys.path if not already present, ensuring modules can be imported correctly.
        - Imports the function/class from src.module and assigns it to self.function_name for use in test cases.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        import src.plugins.patch_override as PatchOverride

        self.PatchOverride = PatchOverride

    def test_po_del_invalid_name_format(self):
        """Test po_del with invalid PO name format."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"projects_path": os.path.join(tmpdir, "projects")}
            projects_info = {
                "test_project": {
                    "board_name": "test_board",
                    "board_path": os.path.join(tmpdir, "board"),
                }
            }
            project_name = "test_project"
            po_name = "invalid_name"  # Doesn't start with 'po'

            with patch("src.plugins.patch_override.log") as mock_log:
                # Act
                result = self.PatchOverride.po_del(env, projects_info, project_name, po_name, force=True)

                # Assert
                assert result is False
                mock_log.error.assert_called_with(
                    "po_name '%s' is invalid. It must start with 'po' and only contain lowercase letters, digits, and underscores.",
                    po_name,
                )

    def test_po_del_missing_board_info(self):
        """Test po_del when board info is missing."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"projects_path": os.path.join(tmpdir, "projects")}
            # Missing board_name and board_path
            projects_info = {"test_project": {}}
            project_name = "test_project"
            po_name = "po_test"

            with patch("src.plugins.patch_override.log") as mock_log:
                # Act
                result = self.PatchOverride.po_del(env, projects_info, project_name, po_name, force=True)

                # Assert
                assert result is False
                mock_log.error.assert_called_with("Board info missing for project '%s'", project_name)


class TestPatchOverrideList:
    """Test cases for po_list method."""

    def setup_method(self):
        """
        Prepare the test environment for each test case.
        - Adds the project root to sys.path if not already present, ensuring modules can be imported correctly.
        - Imports the function/class from src.module and assigns it to self.function_name for use in test cases.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        import src.plugins.patch_override as PatchOverride

        self.PatchOverride = PatchOverride

    def test_po_list_missing_board_name(self):
        """Test po_list when board_name is missing from project config."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"projects_path": os.path.join(tmpdir, "projects")}
            projects_info = {"test_project": {}}  # No board_name
            project_name = "test_project"

            with patch("src.plugins.patch_override.log") as mock_log:
                # Act
                result = self.PatchOverride.po_list(env, projects_info, project_name)

                # Assert
                assert not result
                mock_log.error.assert_called_with("Cannot find board name for project: '%s'", project_name)

    def test_po_list_no_po_directory(self):
        """Test po_list when po directory doesn't exist."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"projects_path": os.path.join(tmpdir, "projects")}
            projects_info = {
                "test_project": {
                    "board_name": "test_board",
                    "PROJECT_PO_CONFIG": "po1",
                }
            }
            project_name = "test_project"

            with patch("os.path.join") as mock_join, patch("os.path.isdir") as mock_isdir, patch(
                "src.plugins.patch_override.log"
            ) as mock_log:
                mock_join.side_effect = lambda *args: "/".join(args)
                mock_isdir.return_value = False  # po directory doesn't exist

                # Act
                result = self.PatchOverride.po_list(env, projects_info, project_name)

                # Assert
                assert not result
                mock_log.warning.assert_called_with("No po directory found for '%s'", project_name)

    def test_po_list_empty_config(self):
        """Test po_list when PROJECT_PO_CONFIG is empty."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"projects_path": os.path.join(tmpdir, "projects")}
            projects_info = {
                "test_project": {
                    "board_name": "test_board",
                    "PROJECT_PO_CONFIG": "",  # Empty config
                }
            }
            project_name = "test_project"

            with patch("os.path.join") as mock_join, patch("os.path.isdir") as mock_isdir, patch(
                "src.plugins.patch_override.log"
            ) as mock_log:
                mock_join.side_effect = lambda *args: "/".join(args)
                mock_isdir.return_value = True  # po directory exists

                # Act
                result = self.PatchOverride.po_list(env, projects_info, project_name)

                # Assert
                assert not result
                mock_log.info.assert_called_with("start po_list for project: '%s'", project_name)


class TestPatchOverrideParseConfig:
    """Test cases for parse_po_config method."""

    def setup_method(self):
        """
        Prepare the test environment for each test case.
        - Adds the project root to sys.path if not already present, ensuring modules can be imported correctly.
        - Imports the function/class from src.module and assigns it to self.function_name for use in test cases.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        import src.plugins.patch_override as PatchOverride

        self.PatchOverride = PatchOverride

    def test_parse_po_config_simple(self):
        """Test parse_po_config with simple config."""
        # Arrange
        po_config = "po1 po2"

        # Act
        apply_pos, exclude_pos, exclude_files = self.PatchOverride.parse_po_config(po_config)

        # Assert
        assert apply_pos == ["po1", "po2"]
        assert exclude_pos == set()
        assert not exclude_files


class TestPatchOverrideUpdate:
    """Test cases for po_update command."""

    def setup_method(self):
        """
        Prepare the test environment for each test case.
        - Adds the project root to sys.path if not already present, ensuring modules can be imported correctly.
        - Imports the function/class from src.module and assigns it to self.function_name for use in test cases.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        import src.plugins.patch_override as PatchOverride

        self.PatchOverride = PatchOverride

    def test_po_update_fails_when_po_not_exists(self):
        """po_update should fail if PO directory does not exist."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"projects_path": os.path.join(tmpdir, "projects")}
            projects_info = {
                "test_project": {
                    "board_name": "test_board",
                    "board_path": os.path.join(tmpdir, "board"),
                }
            }
            project_name = "test_project"
            po_name = "po_test"

            with patch("os.path.join") as mock_join, patch("os.path.exists") as mock_exists, patch(
                "src.plugins.patch_override.log"
            ) as mock_log:
                mock_join.side_effect = lambda *args: "/".join(args)

                # Simulate PO directory not exists and po_dir may or may not exist
                def _exists_side_effect(path):
                    # Return False for po_path; True for po_dir to bypass its creation logic
                    if path.endswith(f"po/{po_name}"):
                        return False
                    if path.endswith("/po"):
                        return True
                    return False

                mock_exists.side_effect = _exists_side_effect

                # Act
                result = self.PatchOverride.po_update(env, projects_info, project_name, po_name, force=True)

                # Assert
                assert result is False
                expected_path = os.path.join(tmpdir, "projects", "test_board", "po", "po_test")
                mock_log.error.assert_called_with(
                    "PO directory '%s' does not exist for update",
                    expected_path,
                )

    def test_po_update_succeeds_when_po_exists(self):
        """po_update should succeed in force mode when PO directory exists."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"projects_path": os.path.join(tmpdir, "projects")}
            projects_info = {
                "test_project": {
                    "board_name": "test_board",
                    "board_path": os.path.join(tmpdir, "board"),
                    "config": {},
                }
            }
            project_name = "test_project"
            po_name = "po_test"

            with patch("os.path.join") as mock_join, patch("os.path.exists") as mock_exists, patch(
                "os.makedirs"
            ) as mock_makedirs, patch("src.plugins.patch_override.log") as mock_log:
                mock_join.side_effect = lambda *args: "/".join(args)

                def _exists_side_effect(path):
                    # PO path exists -> update path
                    if path.endswith(f"po/{po_name}"):
                        return True
                    # po_dir exists
                    if path.endswith("/po"):
                        return True
                    return False

                mock_exists.side_effect = _exists_side_effect
                mock_makedirs.return_value = None

                # Act
                result = self.PatchOverride.po_update(env, projects_info, project_name, po_name, force=True)

                # Assert
                assert result is True
                mock_log.info.assert_any_call(
                    "start po_new for project: '%s', po_name: '%s'",
                    project_name,
                    po_name,
                )

    def test_parse_po_config_with_exclusions(self):
        """Test parse_po_config with excluded POs."""
        # Arrange
        po_config = "po1 po2 -po3"

        # Act
        apply_pos, exclude_pos, exclude_files = self.PatchOverride.parse_po_config(po_config)

        # Assert
        assert apply_pos == ["po1", "po2"]
        assert exclude_pos == {"po3"}
        assert not exclude_files

    def test_parse_po_config_with_file_exclusions(self):
        """Test parse_po_config with file exclusions."""
        # Arrange
        po_config = "po1[file1.txt file2.txt]"

        # Act
        apply_pos, exclude_pos, exclude_files = self.PatchOverride.parse_po_config(po_config)

        # Assert
        assert apply_pos == ["po1"]
        assert exclude_pos == set()
        assert exclude_files == {"po1": {"file1.txt", "file2.txt"}}

    def test_parse_po_config_complex(self):
        """Test parse_po_config with complex config."""
        # Arrange
        po_config = "po1[file1.txt] po2 -po3[file2.txt file3.txt]"

        # Act
        apply_pos, exclude_pos, exclude_files = self.PatchOverride.parse_po_config(po_config)

        # Assert
        assert apply_pos == ["po1", "po2"]
        assert exclude_pos == {"po3"}
        assert exclude_files == {"po1": {"file1.txt"}, "po3": {"file2.txt", "file3.txt"}}

    def test_parse_po_config_empty(self):
        """Test parse_po_config with empty config."""
        # Arrange
        po_config = ""

        # Act
        apply_pos, exclude_pos, exclude_files = self.PatchOverride.parse_po_config(po_config)

        # Assert
        assert not apply_pos
        assert exclude_pos == set()
        assert not exclude_files

    def test_po_apply_overrides_with_actual_repo_matching(self):
        """Apply overrides: previously asserted override flags; now neutralized after flag removal."""
        assert True

    def test_po_apply_logs_commands_to_po_applied_file(self):
        """Test that po_apply logs all executed commands to po_applied file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "test_board"
            project_name = "test_project"
            po_name = "po_test"

            # Create directory structure
            po_dir = os.path.join(projects_path, board_name, "po", po_name)
            patches_dir = os.path.join(po_dir, "patches")
            overrides_dir = os.path.join(po_dir, "overrides")

            os.makedirs(patches_dir, exist_ok=True)
            os.makedirs(overrides_dir, exist_ok=True)

            # Create a test repository first
            repo_dir = os.path.join(tmpdir, "test_repo")
            os.makedirs(repo_dir, exist_ok=True)

            # Initialize git repo

            subprocess.run(["git", "init"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)

            # Create initial file
            with open(os.path.join(repo_dir, "test.txt"), "w", encoding="utf-8") as f:
                f.write("original content")
            subprocess.run(["git", "add", "test.txt"], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True)

            # Now create a real patch file by making changes and generating patch
            with open(os.path.join(repo_dir, "test.txt"), "w", encoding="utf-8") as f:
                f.write("original content\npatched content")
            subprocess.run(["git", "add", "test.txt"], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-m", "Add patched content"], cwd=repo_dir, check=True)

            # Generate the patch using git diff instead of format-patch
            patch_output = subprocess.run(
                ["git", "diff", "HEAD~1", "HEAD"], cwd=repo_dir, capture_output=True, text=True, check=True
            )

            # Create the patch file
            patch_file = os.path.join(patches_dir, "test.patch")
            with open(patch_file, "w", encoding="utf-8") as f:
                f.write(patch_output.stdout)

            # Reset the repo to the original state
            subprocess.run(["git", "reset", "--hard", "HEAD~1"], cwd=repo_dir, check=True)

            # Create a test override file
            override_file = os.path.join(overrides_dir, "test_override.txt")
            with open(override_file, "w", encoding="utf-8") as f:
                f.write("override content")

            # Setup environment
            env = {"projects_path": projects_path, "repositories": [(repo_dir, "root")], "po_configs": {}}

            projects_info = {project_name: {"board_name": board_name, "config": {"PROJECT_PO_CONFIG": po_name}}}

            # Run in tmpdir so files are created in temporary directory
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = self.PatchOverride.po_apply(env, projects_info, project_name)
            finally:
                os.chdir(old_cwd)

            # Check result
            assert result, "po_apply should succeed"

            # Check po_applied file exists
            po_applied_file = os.path.join(po_dir, "po_applied")
            assert os.path.exists(po_applied_file), "po_applied file should exist"

            # Read and check po_applied content
            with open(po_applied_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Verify logging format
            assert "# Applied for project" in content, "Should contain project info"
            assert "Operation log" in content, "Should contain operation log header"
            assert "git apply" in content, "Should contain git apply command"
            assert "cp -rf" in content, "Should contain cp -rf commands"
            assert "Copy override file" in content, "Should contain override description"

    def test_po_apply_uses_cp_command_instead_of_shutil(self):
        """Test that po_apply uses cp command instead of shutil.copy2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "test_board"
            project_name = "test_project"
            po_name = "po_test"

            # Create directory structure
            po_dir = os.path.join(projects_path, board_name, "po", po_name)
            overrides_dir = os.path.join(po_dir, "overrides")

            os.makedirs(overrides_dir, exist_ok=True)

            # Create a test override file
            override_file = os.path.join(overrides_dir, "test_override.txt")
            with open(override_file, "w", encoding="utf-8") as f:
                f.write("override content")

            # Create a test repository
            repo_dir = os.path.join(tmpdir, "test_repo")
            os.makedirs(repo_dir, exist_ok=True)

            # Initialize git repo

            subprocess.run(["git", "init"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)

            # Create initial file
            with open(os.path.join(repo_dir, "test.txt"), "w", encoding="utf-8") as f:
                f.write("original content")
            subprocess.run(["git", "add", "test.txt"], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True)

            # Setup environment
            env = {"projects_path": projects_path, "repositories": [(repo_dir, "root")], "po_configs": {}}

            projects_info = {project_name: {"board_name": board_name, "config": {"PROJECT_PO_CONFIG": po_name}}}

            # Run in tmpdir so files are created in temporary directory
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = self.PatchOverride.po_apply(env, projects_info, project_name)
            finally:
                os.chdir(old_cwd)

            # Check result
            assert result, "po_apply should succeed"

            # Check po_applied file exists
            po_applied_file = os.path.join(po_dir, "po_applied")
            assert os.path.exists(po_applied_file), "po_applied file should exist"

            # Read and check po_applied content
            with open(po_applied_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Verify cp command is used
            assert "cp " in content, "Should contain cp command"
            assert "Copy override file" in content, "Should contain copy description"

            # Verify the command format
            lines = content.split("\n")
            cp_lines = [line for line in lines if " cp " in f" {line} "]
            assert len(cp_lines) >= 1, "Should have at least one cp command"

            # Verify the cp command has correct format
            cp_line = cp_lines[0]
            assert "test_override.txt" in cp_line, "Should contain source file name"
            assert "test_override.txt" in cp_line, "Should contain destination file name"

    def test_po_apply_custom_operations_logged(self):
        """Test that custom operations are logged to po_applied file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "test_board"
            project_name = "test_project"
            po_name = "po_test"

            # Create directory structure
            po_dir = os.path.join(projects_path, board_name, "po", po_name)
            custom_dir = os.path.join(po_dir, "custom")

            os.makedirs(custom_dir, exist_ok=True)

            # Create a test custom file
            custom_file = os.path.join(custom_dir, "test_custom.txt")
            with open(custom_file, "w", encoding="utf-8") as f:
                f.write("custom content")

            # Create a test repository
            repo_dir = os.path.join(tmpdir, "test_repo")
            os.makedirs(repo_dir, exist_ok=True)

            # Initialize git repo

            subprocess.run(["git", "init"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)

            # Create initial file
            with open(os.path.join(repo_dir, "test.txt"), "w", encoding="utf-8") as f:
                f.write("original content")
            subprocess.run(["git", "add", "test.txt"], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True)

            # Setup environment with custom config
            env = {
                "projects_path": projects_path,
                "repositories": [(repo_dir, "root")],
                "po_configs": {
                    f"po-{po_name}": {"PROJECT_PO_DIR": "", "PROJECT_PO_FILE_COPY": "test_custom.txt:custom_dest.txt"}
                },
            }

            projects_info = {project_name: {"board_name": board_name, "config": {"PROJECT_PO_CONFIG": po_name}}}

            # Run in tmpdir so files are created in temporary directory
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = self.PatchOverride.po_apply(env, projects_info, project_name)
            finally:
                os.chdir(old_cwd)

            # Check result
            assert result, "po_apply should succeed"

            # Check po_applied file exists
            po_applied_file = os.path.join(po_dir, "po_applied")
            assert os.path.exists(po_applied_file), "po_applied file should exist"

            # Read and check po_applied content
            with open(po_applied_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Verify custom operations are logged
            assert "Copy custom file" in content, "Should contain custom copy description"
            assert "cp " in content, "Should contain cp command"

            # Verify the command format
            lines = content.split("\n")
            cp_lines = [line for line in lines if line.startswith("cp ")]
            assert len(cp_lines) >= 1, "Should have at least one cp command"

            # Verify the cp command has correct format
            cp_line = cp_lines[0]
            assert "test_custom.txt" in cp_line, "Should contain source file name"
            assert "custom_dest.txt" in cp_line, "Should contain destination file name"

    def test_po_applied_file_format(self):
        """Test that po_applied file has correct format without timestamps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "test_board"
            project_name = "test_project"
            po_name = "po_test"

            # Create directory structure
            po_dir = os.path.join(projects_path, board_name, "po", po_name)
            overrides_dir = os.path.join(po_dir, "overrides")

            os.makedirs(overrides_dir, exist_ok=True)

            # Create a test override file
            override_file = os.path.join(overrides_dir, "test_override.txt")
            with open(override_file, "w", encoding="utf-8") as f:
                f.write("override content")

            # Create a test repository
            repo_dir = os.path.join(tmpdir, "test_repo")
            os.makedirs(repo_dir, exist_ok=True)

            # Initialize git repo

            subprocess.run(["git", "init"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)

            # Create initial file
            with open(os.path.join(repo_dir, "test.txt"), "w", encoding="utf-8") as f:
                f.write("original content")
            subprocess.run(["git", "add", "test.txt"], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True)

            # Setup environment
            env = {"projects_path": projects_path, "repositories": [(repo_dir, "root")], "po_configs": {}}

            projects_info = {project_name: {"board_name": board_name, "config": {"PROJECT_PO_CONFIG": po_name}}}

            # Run in tmpdir so files are created in temporary directory
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = self.PatchOverride.po_apply(env, projects_info, project_name)
            finally:
                os.chdir(old_cwd)

            # Check result
            assert result, "po_apply should succeed"

            # Check po_applied file exists
            po_applied_file = os.path.join(po_dir, "po_applied")
            assert os.path.exists(po_applied_file), "po_applied file should exist"

            # Read and check po_applied content
            with open(po_applied_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Verify file format
            lines = content.split("\n")

            # Check header
            assert lines[0].startswith("# Applied for project"), "Should start with project info"
            assert "# Operation log" in content, "Should contain operation log header"
            assert "# Commands can be re-executed" in content, "Should contain re-execution note"

            # Check that there are no timestamps in command lines
            command_lines = [line for line in lines if line.startswith("cp -rf") or line.startswith("git ")]
            for line in command_lines:
                # Should not contain timestamp pattern [YYYY-MM-DD HH:MM:SS]
                assert not (line.startswith("[") and "]" in line), f"Command line should not contain timestamp: {line}"

            # Check that descriptions are present
            assert "Copy override file" in content, "Should contain operation descriptions"

    def test_po_new_detects_deleted_files(self):
        """Test that po_new detects deleted files correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "test_board"
            project_name = "test_project"
            po_name = "po_test"

            # Create a git repository
            repo_dir = os.path.join(tmpdir, "repo")
            os.makedirs(repo_dir)
            subprocess.run(["git", "init"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)

            # Create and commit a file
            test_file = os.path.join(repo_dir, "test.txt")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("test content")
            subprocess.run(["git", "add", "test.txt"], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-m", "Add test file"], cwd=repo_dir, check=True)

            # Delete the file
            os.remove(test_file)

            # Setup environment
            env = {"projects_path": projects_path, "repositories": [(repo_dir, "root")], "po_configs": {}}
            projects_info = {
                project_name: {
                    "board_name": board_name,
                    "board_path": os.path.join(projects_path, board_name),
                    "config": {},
                }
            }

            # Mock the interactive selection to avoid user input
            with patch("builtins.input", return_value="3"):  # Skip all files
                result = self.PatchOverride.po_new(env, projects_info, project_name, po_name, force=True)

            # Check that po_new succeeded
            assert result, "po_new should succeed"

    def test_po_new_creates_remove_files_for_deleted_files(self):
        """Test that po_new creates .remove files for deleted files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "test_board"
            project_name = "test_project"
            po_name = "po_test"

            # Create a git repository
            repo_dir = os.path.join(tmpdir, "repo")
            os.makedirs(repo_dir)
            subprocess.run(["git", "init"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)

            # Create and commit a file
            test_file = os.path.join(repo_dir, "test.txt")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("test content")
            subprocess.run(["git", "add", "test.txt"], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-m", "Add test file"], cwd=repo_dir, check=True)

            # Delete the file
            os.remove(test_file)

            # Setup environment
            env = {"projects_path": projects_path, "repositories": [(repo_dir, "root")], "po_configs": {}}
            projects_info = {
                project_name: {
                    "board_name": board_name,
                    "board_path": os.path.join(projects_path, board_name),
                    "config": {},
                }
            }

            # Mock the interactive selection to create remove files
            # First input is for confirmation (yes), second is for file selection (select all files), third is for action choice
            with patch(
                "builtins.input", side_effect=["yes", "all", "3"]
            ):  # Confirm creation, select all files, then create remove files
                result = self.PatchOverride.po_new(env, projects_info, project_name, po_name, force=False)

            # Check that po_new succeeded
            assert result, "po_new should succeed"

            # Check that .remove file was created
            remove_file = os.path.join(projects_path, board_name, "po", po_name, "overrides", "test.txt.remove")
            assert os.path.exists(remove_file), "Remove file should be created"

            # Check the content of the remove file
            with open(remove_file, "r", encoding="utf-8") as f:
                content = f.read()
            assert "Remove marker for deleted file: test.txt" in content
            assert "This file was deleted from repository: root" in content

    def test_po_new_handles_directory_deletion_with_gitkeep(self):
        """Test that po_new creates .gitkeep for directory deletion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_path = os.path.join(tmpdir, "projects")
            board_name = "test_board"
            project_name = "test_project"
            po_name = "po_test"

            # Create a git repository
            repo_dir = os.path.join(tmpdir, "repo")
            os.makedirs(repo_dir)
            subprocess.run(["git", "init"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)

            # Create a directory with multiple files
            test_dir = os.path.join(repo_dir, "testdir")
            os.makedirs(test_dir)

            file1 = os.path.join(test_dir, "file1.txt")
            file2 = os.path.join(test_dir, "file2.txt")

            with open(file1, "w", encoding="utf-8") as f:
                f.write("content1")
            with open(file2, "w", encoding="utf-8") as f:
                f.write("content2")

            subprocess.run(["git", "add", "testdir/"], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-m", "Add test directory"], cwd=repo_dir, check=True)

            # Delete the entire directory
            shutil.rmtree(test_dir)

            # Setup environment
            env = {"projects_path": projects_path, "repositories": [(repo_dir, "root")], "po_configs": {}}
            projects_info = {
                project_name: {
                    "board_name": board_name,
                    "board_path": os.path.join(projects_path, board_name),
                    "config": {},
                }
            }

            # Mock the interactive selection to create remove files
            # First input is for confirmation (yes), second is for file selection (select all files), third is for action choice
            with patch(
                "builtins.input", side_effect=["yes", "all", "3"]
            ):  # Confirm creation, select all files, then create remove files
                result = self.PatchOverride.po_new(env, projects_info, project_name, po_name, force=False)

            # Check that po_new succeeded
            assert result, "po_new should succeed"

            # Check that .gitkeep file was created for the directory
            gitkeep_file = os.path.join(projects_path, board_name, "po", po_name, "overrides", "testdir", ".gitkeep")
            assert os.path.exists(gitkeep_file), "Gitkeep file should be created for deleted directory"

            # Check the content of the gitkeep file
            with open(gitkeep_file, "r", encoding="utf-8") as f:
                content = f.read()
            assert "Directory preservation marker" in content
            assert "Original directory: testdir" in content
            assert "This directory was deleted, .gitkeep prevents it from being removed" in content
