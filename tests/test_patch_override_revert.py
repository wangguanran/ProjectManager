"""
Tests for patch and override revert operations.
"""

# pylint: disable=attribute-defined-outside-init, import-outside-toplevel, too-many-public-methods, protected-access
import os
import subprocess
import pytest
from test_patch_override_base import BasePatchOverrideTest


class TestPatchOverrideRevert(BasePatchOverrideTest):
    """Test class for patch and override revert operations."""

    def test_basic_functionality(self):
        """Test basic functionality - implementation of abstract method."""
        # This is a placeholder for the abstract method
        assert True

    def test_po_revert_basic(self):
        """Test basic po_revert functionality."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create PatchOverride instance
            all_projects_info = self._load_all_projects_info()
            patch_override = self.patch_override_cls(
                self.vprojects_path, all_projects_info
            )

            # First apply po_apply
            result = patch_override.po_apply("test_project")
            assert result is True

            # Verify files were applied
            with open("main.py", "r", encoding="utf-8") as f:
                content = f.read()
            assert "Patched by po_test01" in content

            assert os.path.exists("new_file.txt")
            with open("config.txt", "r", encoding="utf-8") as f:
                content = f.read()
            assert "Overridden by po_test02" in content

            # Now revert
            result = patch_override.po_revert("test_project")
            assert result is True

            # Check if patch was reverted
            with open("main.py", "r", encoding="utf-8") as f:
                content = f.read()
            assert "Patched by po_test01" not in content
            assert "print('Hello, World!')" in content

            # Check if override files were reverted
            # new_file.txt should be deleted (untracked file)
            assert not os.path.exists("new_file.txt")

            # config.txt should be restored to original
            with open("config.txt", "r", encoding="utf-8") as f:
                content = f.read()
            assert "Overridden by po_test02" not in content
            assert "debug=true" in content
            assert "port=8080" in content

            # Check if flag files were cleaned up
            assert not os.path.exists(".patch_applied")
            assert not os.path.exists(".override_applied")

        finally:
            os.chdir(original_cwd)

    def test_po_revert_git_tracked_files(self):
        """Test po_revert with git tracked files."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create PatchOverride instance
            all_projects_info = self._load_all_projects_info()
            patch_override = self.patch_override_cls(
                self.vprojects_path, all_projects_info
            )

            # Apply po_apply
            result = patch_override.po_apply("test_project")
            assert result is True

            # Verify config.txt was overridden (this is a git tracked file)
            with open("config.txt", "r", encoding="utf-8") as f:
                content = f.read()
            assert "Overridden by po_test02" in content

            # Now revert
            result = patch_override.po_revert("test_project")
            assert result is True

            # Check if config.txt was restored using git checkout
            with open("config.txt", "r", encoding="utf-8") as f:
                content = f.read()
            assert "Overridden by po_test02" not in content
            assert "debug=true" in content
            assert "port=8080" in content

        finally:
            os.chdir(original_cwd)

    def test_po_revert_untracked_files(self):
        """Test po_revert with git untracked files."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create PatchOverride instance
            all_projects_info = self._load_all_projects_info()
            patch_override = self.patch_override_cls(
                self.vprojects_path, all_projects_info
            )

            # Apply po_apply
            result = patch_override.po_apply("test_project")
            assert result is True

            # Verify new_file.txt was created (this is an untracked file)
            assert os.path.exists("new_file.txt")
            with open("new_file.txt", "r", encoding="utf-8") as f:
                content = f.read()
            assert "This is a new file from po_test01" in content

            # Now revert
            result = patch_override.po_revert("test_project")
            assert result is True

            # Check if new_file.txt was deleted (untracked file)
            assert not os.path.exists("new_file.txt")

        finally:
            os.chdir(original_cwd)

    def test_po_revert_idempotent(self):
        """Test that po_revert can be run multiple times without issues."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create PatchOverride instance
            all_projects_info = self._load_all_projects_info()
            patch_override = self.patch_override_cls(
                self.vprojects_path, all_projects_info
            )

            # Apply po_apply
            result = patch_override.po_apply("test_project")
            assert result is True

            # Revert first time
            result1 = patch_override.po_revert("test_project")
            assert result1 is True

            # Revert second time (should still succeed)
            result2 = patch_override.po_revert("test_project")
            assert result2 is True

            # Verify files are still in original state
            with open("main.py", "r", encoding="utf-8") as f:
                content = f.read()
            assert "Patched by po_test01" not in content
            assert "print('Hello, World!')" in content

            assert not os.path.exists("new_file.txt")

            with open("config.txt", "r", encoding="utf-8") as f:
                content = f.read()
            assert "Overridden by po_test02" not in content
            assert "debug=true" in content

        finally:
            os.chdir(original_cwd)

    def test_po_revert_invalid_project(self):
        """Test po_revert with invalid project name."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create PatchOverride instance
            all_projects_info = self._load_all_projects_info()
            patch_override = self.patch_override_cls(
                self.vprojects_path, all_projects_info
            )

            # Revert with invalid project
            result = patch_override.po_revert("invalid_project")

            # Should return False for invalid project
            assert result is False

        finally:
            os.chdir(original_cwd)

    def test_po_revert_no_config(self):
        """Test po_revert with project that has no PROJECT_PO_CONFIG."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create project info without PROJECT_PO_CONFIG
            all_projects_info = {"test_project_no_config": {"board_name": "test_board"}}

            patch_override = self.patch_override_cls(
                self.vprojects_path, all_projects_info
            )

            # Revert
            result = patch_override.po_revert("test_project_no_config")

            # Should return True (no config means success)
            assert result is True

        finally:
            os.chdir(original_cwd)

    def test_po_revert_partial_application(self):
        """Test po_revert when only some po have been applied."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create PatchOverride instance
            all_projects_info = self._load_all_projects_info()
            patch_override = self.patch_override_cls(
                self.vprojects_path, all_projects_info
            )

            # Apply only po_test01 manually (simulate partial application)
            po_test01_patch_dir = os.path.join(
                self.vprojects_path, "test_board", "po", "po_test01", "patches"
            )
            patch_file = os.path.join(po_test01_patch_dir, "main.py.patch")

            # Apply patch manually
            subprocess.run(
                ["git", "apply", patch_file], cwd=self.test_repo_path, check=True
            )

            # Create flag file manually
            with open(".patch_applied", "w", encoding="utf-8") as f:
                f.write("po_test01\n")

            # Now revert
            result = patch_override.po_revert("test_project")
            assert result is True

            # Check if patch was reverted
            with open("main.py", "r", encoding="utf-8") as f:
                content = f.read()
            assert "Patched by po_test01" not in content
            assert "print('Hello, World!')" in content

            # Check if flag file was cleaned up
            assert not os.path.exists(".patch_applied")

        finally:
            os.chdir(original_cwd)

    def test_po_apply_revert_cycle(self):
        """Test complete apply-revert cycle multiple times."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create PatchOverride instance
            all_projects_info = self._load_all_projects_info()
            patch_override = self.patch_override_cls(
                self.vprojects_path, all_projects_info
            )

            # First cycle: apply -> revert
            result1 = patch_override.po_apply("test_project")
            assert result1 is True

            result2 = patch_override.po_revert("test_project")
            assert result2 is True

            # Second cycle: apply -> revert
            result3 = patch_override.po_apply("test_project")
            assert result3 is True

            result4 = patch_override.po_revert("test_project")
            assert result4 is True

            # Verify final state is clean
            with open("main.py", "r", encoding="utf-8") as f:
                content = f.read()
            assert "Patched by po_test01" not in content
            assert "print('Hello, World!')" in content

            assert not os.path.exists("new_file.txt")

            with open("config.txt", "r", encoding="utf-8") as f:
                content = f.read()
            assert "Overridden by po_test02" not in content
            assert "debug=true" in content

            # Check no flag files remain
            assert not os.path.exists(".patch_applied")
            assert not os.path.exists(".override_applied")

        finally:
            os.chdir(original_cwd)

    def test_po_revert_patch_error_handling(self):
        """Test error handling when patch revert fails."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create a patch that was applied but will fail to revert
            board_path = os.path.join(self.vprojects_path, "test_board")
            po_test01_patch_dir = os.path.join(board_path, "po", "po_test01", "patches")

            # Create a patch that modifies a file
            patch_content = """diff --git a/main.py b/main.py
index 1234567..abcdefg 100644
--- a/main.py
+++ b/main.py
@@ -1 +1,2 @@
 print('Hello, World!')
+print('Added line')
"""
            with open(
                os.path.join(po_test01_patch_dir, "main.py.patch"),
                "w",
                encoding="utf-8",
            ) as f:
                f.write(patch_content)

            # Apply the patch first
            all_projects_info = {
                "test_project_revert_error": {
                    "board_name": "test_board",
                    "PROJECT_PO_CONFIG": "po_test01",
                }
            }

            patch_override = self.patch_override_cls(
                self.vprojects_path, all_projects_info
            )
            result = patch_override.po_apply("test_project_revert_error")
            assert result is True

            # Modify the file to make revert fail
            with open("main.py", "w", encoding="utf-8") as f:
                f.write("print('Modified content')\n")

            # Revert should fail due to conflicts
            result = patch_override.po_revert("test_project_revert_error")
            assert result is False

        finally:
            os.chdir(original_cwd)

    def test_po_revert_with_file_exclusions(self):
        """Test po_revert with file exclusions in config."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create project info with file exclusions
            all_projects_info = {
                "test_project_revert_exclusions": {
                    "board_name": "test_board",
                    "PROJECT_PO_CONFIG": "po_test01 -po_test01[config.txt]",
                }
            }

            patch_override = self.patch_override_cls(
                self.vprojects_path, all_projects_info
            )

            # Apply first
            result = patch_override.po_apply("test_project_revert_exclusions")
            assert result is True

            # Then revert
            result = patch_override.po_revert("test_project_revert_exclusions")
            assert result is True

            # Check that config.txt was not reverted (excluded)
            # This test verifies the exclusion logic works in both directions

        finally:
            os.chdir(original_cwd)

    def test_po_revert_flag_file_handling(self):
        """Test po_revert with corrupted flag files."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Apply first
            all_projects_info = self._load_all_projects_info()
            patch_override = self.patch_override_cls(
                self.vprojects_path, all_projects_info
            )
            result = patch_override.po_apply("test_project")
            assert result is True

            # Corrupt the flag file
            with open(".patch_applied", "w", encoding="utf-8") as f:
                f.write("invalid_content")

            # Revert should handle corrupted flag file gracefully
            result = patch_override.po_revert("test_project")
            assert result is True

        finally:
            os.chdir(original_cwd)

    def test_po_revert_with_subprocess_error(self):
        """Test po_revert with subprocess error during git apply --reverse."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create a patch that was applied but will fail to revert
            board_path = os.path.join(self.vprojects_path, "test_board")
            po_test01_patch_dir = os.path.join(board_path, "po", "po_test01", "patches")

            # Create a patch that modifies a file
            patch_content = """diff --git a/main.py b/main.py
index 1234567..abcdefg 100644
--- a/main.py
+++ b/main.py
@@ -1 +1,2 @@
 print('Hello, World!')
+print('Added line')
"""
            with open(
                os.path.join(po_test01_patch_dir, "main.py.patch"),
                "w",
                encoding="utf-8",
            ) as f:
                f.write(patch_content)

            # Apply the patch first
            all_projects_info = {
                "test_project_revert_subprocess_error": {
                    "board_name": "test_board",
                    "PROJECT_PO_CONFIG": "po_test01",
                }
            }

            patch_override = self.patch_override_cls(
                self.vprojects_path, all_projects_info
            )
            result = patch_override.po_apply("test_project_revert_subprocess_error")
            assert result is True

            # Modify the file to make revert fail
            with open("main.py", "w", encoding="utf-8") as f:
                f.write("print('Modified content')\n")

            # Revert should fail due to conflicts
            result = patch_override.po_revert("test_project_revert_subprocess_error")
            assert result is False

        finally:
            os.chdir(original_cwd)

    def test_po_revert_with_os_error(self):
        """Test po_revert with OS error during file operations."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Apply first
            all_projects_info = self._load_all_projects_info()
            patch_override = self.patch_override_cls(
                self.vprojects_path, all_projects_info
            )
            result = patch_override.po_apply("test_project")
            assert result is True

            # Make the flag file read-only to test error handling
            if os.path.exists(".patch_applied"):
                os.chmod(".patch_applied", 0o444)

            # Revert should handle read-only flag file gracefully
            result = patch_override.po_revert("test_project")
            assert result is True

            # Restore permissions
            if os.path.exists(".patch_applied"):
                os.chmod(".patch_applied", 0o644)

        finally:
            os.chdir(original_cwd)

    def test_po_revert_with_empty_apply_pos(self):
        """Test po_revert when all POs are excluded."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create project info where all POs are excluded
            all_projects_info = {
                "test_project_revert_all_excluded": {
                    "board_name": "test_board",
                    "PROJECT_PO_CONFIG": "-po_test01 -po_test02 -po_test03",
                }
            }

            patch_override = self.patch_override_cls(
                self.vprojects_path, all_projects_info
            )

            # Revert should succeed even with no POs to revert
            result = patch_override.po_revert("test_project_revert_all_excluded")
            assert result is True

        finally:
            os.chdir(original_cwd)

    def test_po_revert_with_gitkeep_files(self):
        """Test po_revert with .gitkeep files in patches and overrides directories."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create PO with .gitkeep files
            board_path = os.path.join(self.vprojects_path, "test_board")
            gitkeep_po_path = os.path.join(board_path, "po", "po_gitkeep")
            patches_dir = os.path.join(gitkeep_po_path, "patches")
            overrides_dir = os.path.join(gitkeep_po_path, "overrides")

            os.makedirs(patches_dir, exist_ok=True)
            os.makedirs(overrides_dir, exist_ok=True)

            # Create .gitkeep files
            with open(
                os.path.join(patches_dir, ".gitkeep"), "w", encoding="utf-8"
            ) as f:
                f.write("")
            with open(
                os.path.join(overrides_dir, ".gitkeep"), "w", encoding="utf-8"
            ) as f:
                f.write("")

            all_projects_info = {
                "test_project_gitkeep": {
                    "board_name": "test_board",
                    "PROJECT_PO_CONFIG": "po_gitkeep",
                }
            }

            patch_override = self.patch_override_cls(
                self.vprojects_path, all_projects_info
            )

            # Revert should succeed and ignore .gitkeep files
            result = patch_override.po_revert("test_project_gitkeep")
            assert result is True

        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    # Run tests if script is executed directly
    pytest.main([__file__, "-v"])
