"""
Tests for patch and override operations.
"""
# pylint: disable=attribute-defined-outside-init, import-outside-toplevel, too-many-public-methods, protected-access
import os
import sys
import tempfile
import shutil
import subprocess
import configparser
import pytest

class TestPatchOverride:
    """Test class for patch and override operations."""
    # temp_dir: str
    # vprojects_path: str
    # test_repo_path: str
    # patch_override_cls: type

    def setup_method(self):
        """Set up test environment before each test."""
        # Add project root to path for imports
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        # Import PatchOverride after path is set
        from src.plugins.patch_override import PatchOverride
        self.temp_dir = tempfile.mkdtemp()
        print(f"Created temporary directory: {self.temp_dir}")
        self.vprojects_path = os.path.join(self.temp_dir, "vprojects")
        self.test_repo_path = os.path.join(self.temp_dir, "test_repo")
        self.patch_override_cls = PatchOverride

        # Create vprojects directory structure
        os.makedirs(self.vprojects_path)

        # Create test git repository
        self._create_test_git_repo()

        # Create test project structure
        self._create_test_project_structure()

        # Mock all_projects_info
        self.all_projects_info = {
            "test_project": {
                "board_name": "test_board",
                "PROJECT_PO_CONFIG": "po_test01 po_test02 -po_test03"
            },
            "test_project_child": {
                "board_name": "test_board",
                "PROJECT_PO_CONFIG": "-po_test01"
            }
        }

        self.patch_override = self.patch_override_cls(self.vprojects_path, self.all_projects_info)

    def teardown_method(self):
        """Clean up test environment after each test."""
        print(f"Cleaning up temporary directory: {self.temp_dir}")
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_git_repo(self):
        """Create a test git repository with some initial files."""
        os.makedirs(self.test_repo_path)

        # Initialize git repository
        subprocess.run(["git", "init"], cwd=self.test_repo_path, check=True)

        # Create initial files
        initial_files = {
            "main.py": "print('Hello, World!')\n",
            "config.txt": "debug=true\nport=8080\n",
            "src/utils.py": "def helper():\n    return 'helper'\n",
            "docs/README.md": "# Test Project\n\nThis is a test project.\n"
        }

        for file_path, content in initial_files.items():
            full_path = os.path.join(self.test_repo_path, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)

        # Add and commit files
        subprocess.run(["git", "add", "."], cwd=self.test_repo_path, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.test_repo_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.test_repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.test_repo_path, check=True)

    def _create_test_project_structure(self):
        """Create test project structure with patches and overrides."""
        board_name = "test_board"
        board_path = os.path.join(self.vprojects_path, board_name)
        os.makedirs(board_path)

        # Create board.ini file
        board_ini = os.path.join(board_path, "board.ini")
        with open(board_ini, 'w', encoding='utf-8') as f:
            f.write("""[test_project]
board_name = test_board
PROJECT_PO_CONFIG = po_test01 po_test02 -po_test03[main.py config.txt]
""")

        # Create po directories
        po_dir = os.path.join(board_path, "po")
        os.makedirs(po_dir)

        # Create po_test01 with patches
        po_test01_path = os.path.join(po_dir, "po_test01")
        patches_dir = os.path.join(po_test01_path, "patches")
        overrides_dir = os.path.join(po_test01_path, "overrides")
        os.makedirs(patches_dir)
        os.makedirs(overrides_dir)

        # Create a patch file
        patch_content = """diff --git a/main.py b/main.py
index 1234567..abcdefg 100644
--- a/main.py
+++ b/main.py
@@ -1 +1,2 @@
 print('Hello, World!')
+print('Patched by po_test01')
"""
        with open(os.path.join(patches_dir, "main.py.patch"), 'w', encoding='utf-8') as f:
            f.write(patch_content)

        # Create an override file
        with open(os.path.join(overrides_dir, "new_file.txt"), 'w', encoding='utf-8') as f:
            f.write("This is a new file from po_test01\n")

        # Create po_test02 with overrides
        po_test02_path = os.path.join(po_dir, "po_test02")
        patches_dir2 = os.path.join(po_test02_path, "patches")
        overrides_dir2 = os.path.join(po_test02_path, "overrides")
        os.makedirs(patches_dir2)
        os.makedirs(overrides_dir2)

        # Create an override for existing file
        with open(os.path.join(overrides_dir2, "config.txt"), 'w', encoding='utf-8') as f:
            f.write("debug=false\nport=9090\n# Overridden by po_test02\n")

        # Create po_test03 (will be excluded)
        po_test03_path = os.path.join(po_dir, "po_test03")
        patches_dir3 = os.path.join(po_test03_path, "patches")
        overrides_dir3 = os.path.join(po_test03_path, "overrides")
        os.makedirs(patches_dir3)
        os.makedirs(overrides_dir3)

        # Create files that should be excluded
        with open(os.path.join(patches_dir3, "main.py.patch"), 'w', encoding='utf-8') as f:
            f.write("This patch should be excluded\n")
        with open(os.path.join(overrides_dir3, "config.txt"), 'w', encoding='utf-8') as f:
            f.write("This override should be excluded\n")

    def _load_all_projects_info(self):
        """Load project information for testing."""
        # This is a simplified version of the project loading logic
        all_projects_info = {
            "test_project": {
                "board_name": "test_board",
                "PROJECT_PO_CONFIG": "po_test01 po_test02 -po_test03[main.py config.txt]"
            }
        }
        return all_projects_info

    def test_po_apply_basic(self):
        """Test basic po_apply functionality."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create PatchOverride instance
            all_projects_info = self._load_all_projects_info()
            patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

            # Apply po_apply
            result = patch_override.po_apply("test_project")

            # Verify result
            assert result is True

            # Check if patch was applied
            with open("main.py", 'r', encoding='utf-8') as f:
                content = f.read()
            assert "Patched by po_test01" in content

            # Check if override files were created
            assert os.path.exists("new_file.txt")
            with open("new_file.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            assert "This is a new file from po_test01" in content

            # Check if config.txt was overridden
            with open("config.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            assert "Overridden by po_test02" in content
            assert "port=9090" in content

            # Check if .patch_applied flag was created
            assert os.path.exists(".patch_applied")
            with open(".patch_applied", 'r', encoding='utf-8') as f:
                applied_pos = f.read().strip().split('\n')
            assert "po_test01" in applied_pos

            # Check if .override_applied flag was created
            assert os.path.exists(".override_applied")
            with open(".override_applied", 'r', encoding='utf-8') as f:
                applied_pos = f.read().strip().split('\n')
            assert "po_test01" in applied_pos
            assert "po_test02" in applied_pos

        finally:
            os.chdir(original_cwd)

    def test_po_apply_exclusion(self):
        """Test that excluded po and files are not applied."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create PatchOverride instance
            all_projects_info = self._load_all_projects_info()
            patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

            # Apply po_apply
            result = patch_override.po_apply("test_project")

            # Verify result
            assert result is True

            # Check that po_test03 files were not applied
            # main.py should not contain po_test03 content
            with open("main.py", 'r', encoding='utf-8') as f:
                content = f.read()
            assert "This patch should be excluded" not in content

            # config.txt should not contain po_test03 content
            with open("config.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            assert "This override should be excluded" not in content

        finally:
            os.chdir(original_cwd)

    def test_po_apply_idempotent(self):
        """Test that po_apply can be run multiple times without issues."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create PatchOverride instance
            all_projects_info = self._load_all_projects_info()
            patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

            # Apply po_apply first time
            result1 = patch_override.po_apply("test_project")
            assert result1 is True

            # Apply po_apply second time
            result2 = patch_override.po_apply("test_project")
            assert result2 is True

            # Verify files are still correct
            with open("main.py", 'r', encoding='utf-8') as f:
                content = f.read()
            assert "Patched by po_test01" in content

            with open("config.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            assert "Overridden by po_test02" in content

        finally:
            os.chdir(original_cwd)

    def test_po_apply_invalid_project(self):
        """Test po_apply with invalid project name."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create PatchOverride instance
            all_projects_info = self._load_all_projects_info()
            patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

            # Apply po_apply with invalid project
            result = patch_override.po_apply("invalid_project")

            # Should return False for invalid project
            assert result is False

        finally:
            os.chdir(original_cwd)

    def test_po_apply_no_config(self):
        """Test po_apply with project that has no PROJECT_PO_CONFIG."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create project info without PROJECT_PO_CONFIG
            all_projects_info = {
                "test_project_no_config": {
                    "board_name": "test_board"
                }
            }

            patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

            # Apply po_apply
            result = patch_override.po_apply("test_project_no_config")

            # Should return True (no config means success)
            assert result is True

        finally:
            os.chdir(original_cwd)

    def test_po_revert_basic(self):
        """Test basic po_revert functionality."""
        # Change to test repository directory
        original_cwd = os.getcwd()
        os.chdir(self.test_repo_path)

        try:
            # Create PatchOverride instance
            all_projects_info = self._load_all_projects_info()
            patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

            # First apply po_apply
            result = patch_override.po_apply("test_project")
            assert result is True

            # Verify files were applied
            with open("main.py", 'r', encoding='utf-8') as f:
                content = f.read()
            assert "Patched by po_test01" in content

            assert os.path.exists("new_file.txt")
            with open("config.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            assert "Overridden by po_test02" in content

            # Now revert
            result = patch_override.po_revert("test_project")
            assert result is True

            # Check if patch was reverted
            with open("main.py", 'r', encoding='utf-8') as f:
                content = f.read()
            assert "Patched by po_test01" not in content
            assert "print('Hello, World!')" in content

            # Check if override files were reverted
            # new_file.txt should be deleted (untracked file)
            assert not os.path.exists("new_file.txt")

            # config.txt should be restored to original
            with open("config.txt", 'r', encoding='utf-8') as f:
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
            patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

            # Apply po_apply
            result = patch_override.po_apply("test_project")
            assert result is True

            # Verify config.txt was overridden (this is a git tracked file)
            with open("config.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            assert "Overridden by po_test02" in content

            # Now revert
            result = patch_override.po_revert("test_project")
            assert result is True

            # Check if config.txt was restored using git checkout
            with open("config.txt", 'r', encoding='utf-8') as f:
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
            patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

            # Apply po_apply
            result = patch_override.po_apply("test_project")
            assert result is True

            # Verify new_file.txt was created (this is an untracked file)
            assert os.path.exists("new_file.txt")
            with open("new_file.txt", 'r', encoding='utf-8') as f:
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
            patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

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
            with open("main.py", 'r', encoding='utf-8') as f:
                content = f.read()
            assert "Patched by po_test01" not in content
            assert "print('Hello, World!')" in content

            assert not os.path.exists("new_file.txt")

            with open("config.txt", 'r', encoding='utf-8') as f:
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
            patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

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
            all_projects_info = {
                "test_project_no_config": {
                    "board_name": "test_board"
                }
            }

            patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

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
            patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

            # Apply only po_test01 manually (simulate partial application)
            po_test01_patch_dir = os.path.join(self.vprojects_path, "test_board", "po", "po_test01", "patches")
            patch_file = os.path.join(po_test01_patch_dir, "main.py.patch")

            # Apply patch manually
            subprocess.run(["git", "apply", patch_file], cwd=self.test_repo_path, check=True)

            # Create flag file manually
            with open(".patch_applied", 'w', encoding='utf-8') as f:
                f.write("po_test01\n")

            # Now revert
            result = patch_override.po_revert("test_project")
            assert result is True

            # Check if patch was reverted
            with open("main.py", 'r', encoding='utf-8') as f:
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
            patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

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
            with open("main.py", 'r', encoding='utf-8') as f:
                content = f.read()
            assert "Patched by po_test01" not in content
            assert "print('Hello, World!')" in content

            assert not os.path.exists("new_file.txt")

            with open("config.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            assert "Overridden by po_test02" not in content
            assert "debug=true" in content

            # Check no flag files remain
            assert not os.path.exists(".patch_applied")
            assert not os.path.exists(".override_applied")

        finally:
            os.chdir(original_cwd)

    def test_po_new_basic(self):
        """Test basic po_new functionality."""
        # Create PatchOverride instance
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Create new PO with force=True to skip interactive prompts
        result = patch_override.po_new("test_project", "po_new_test", force=True)
        assert result is True

        # Verify directory structure was created
        board_path = os.path.join(self.vprojects_path, "test_board")
        po_path = os.path.join(board_path, "po", "po_new_test")
        patches_dir = os.path.join(po_path, "patches")
        overrides_dir = os.path.join(po_path, "overrides")

        assert os.path.exists(po_path)
        assert os.path.isdir(po_path)
        assert os.path.exists(patches_dir)
        assert os.path.isdir(patches_dir)
        assert os.path.exists(overrides_dir)
        assert os.path.isdir(overrides_dir)

        # Verify .gitkeep files were created
        assert os.path.exists(os.path.join(patches_dir, ".gitkeep"))
        assert os.path.exists(os.path.join(overrides_dir, ".gitkeep"))

    def test_po_new_existing_po(self):
        """Test po_new with existing PO directory."""
        # Create PatchOverride instance
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Create new PO
        result = patch_override.po_new("test_project", "po_existing_test", force=True)
        assert result is True

        # Try to create the same PO again (should fail now)
        result = patch_override.po_new("test_project", "po_existing_test", force=True)
        assert result is False  # Should fail because PO already exists

        # Verify directory structure still exists
        board_path = os.path.join(self.vprojects_path, "test_board")
        po_path = os.path.join(board_path, "po", "po_existing_test")
        patches_dir = os.path.join(po_path, "patches")
        overrides_dir = os.path.join(po_path, "overrides")

        assert os.path.exists(po_path)
        assert os.path.exists(patches_dir)
        assert os.path.exists(overrides_dir)

    def test_po_new_force_parameter(self):
        """Test po_new with force parameter."""
        # Create PatchOverride instance
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Test with force=True (should work in test environment)
        result = patch_override.po_new("test_project", "po_force_test", force=True)
        assert result is True

        # Verify directory was created
        board_path = os.path.join(self.vprojects_path, "test_board")
        po_path = os.path.join(board_path, "po", "po_force_test")
        assert os.path.exists(po_path)

    def test_po_new_find_repositories_single_git(self):
        """Test __find_repositories with single git repository."""
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Create a git repository in the current working directory (project root)
        # This simulates the new behavior where we look for git repos from current directory
        original_cwd = os.getcwd()
        try:
            # Change to a temporary directory to test
            test_dir = tempfile.mkdtemp()
            os.chdir(test_dir)

            # Create a git repository in the current directory
            subprocess.run(["git", "init"], cwd=test_dir, check=True)

            # Create a test file
            test_file = os.path.join(test_dir, "test.txt")
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write("test content\n")

            subprocess.run(["git", "add", "test.txt"], cwd=test_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=test_dir, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=test_dir, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=test_dir, check=True)

            # Test repository detection
            board_path = os.path.join(self.vprojects_path, "test_board")
            repositories = patch_override._PatchOverride__find_repositories(board_path)

            # Should find one repository (the current directory)
            assert len(repositories) == 1
            repo_path, repo_name = repositories[0]
            assert repo_path == test_dir
            assert repo_name == "root"

        finally:
            os.chdir(original_cwd)
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_po_new_find_repositories_repo_manifest(self):
        """Test __find_repositories with .repo manifest."""
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Create .repo manifest structure
        board_path = os.path.join(self.vprojects_path, "test_board")
        repo_dir = os.path.join(board_path, ".repo")
        os.makedirs(repo_dir)

        # Create manifest.xml
        manifest_content = """<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <project path="." name="root"/>
  <project path="subproject1" name="sub1"/>
  <project path="subproject2" name="sub2"/>
</manifest>"""

        with open(os.path.join(repo_dir, "manifest.xml"), 'w', encoding='utf-8') as f:
            f.write(manifest_content)

        # Create git repositories for the projects
        subproject1_path = os.path.join(board_path, "subproject1")
        subproject2_path = os.path.join(board_path, "subproject2")

        os.makedirs(subproject1_path)
        os.makedirs(subproject2_path)

        subprocess.run(["git", "init"], cwd=board_path, check=True)
        subprocess.run(["git", "init"], cwd=subproject1_path, check=True)
        subprocess.run(["git", "init"], cwd=subproject2_path, check=True)

        # Change to board_path directory for testing
        original_cwd = os.getcwd()
        try:
            os.chdir(board_path)

            # Test repository detection
            repositories = patch_override._PatchOverride__find_repositories(board_path)

            # Should find 3 repositories
            assert len(repositories) == 3

            repo_paths = [repo[0] for repo in repositories]
            repo_names = [repo[1] for repo in repositories]

            # Check that all expected repositories are found
            # Note: root repository path might be normalized, so we check by name instead
            assert "root" in repo_names
            assert "subproject1" in repo_names
            assert "subproject2" in repo_names

            # Verify the actual paths exist
            for repo_path in repo_paths:
                assert os.path.exists(repo_path)
                assert os.path.exists(os.path.join(repo_path, ".git"))
        finally:
            os.chdir(original_cwd)

    def test_po_new_find_repositories_recursive(self):
        """Test __find_repositories with recursive git repository discovery."""
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Create nested git repositories
        board_path = os.path.join(self.vprojects_path, "test_board")
        nested_repo1 = os.path.join(board_path, "nested", "repo1")
        nested_repo2 = os.path.join(board_path, "nested", "repo2")

        os.makedirs(nested_repo1)
        os.makedirs(nested_repo2)

        subprocess.run(["git", "init"], cwd=nested_repo1, check=True)
        subprocess.run(["git", "init"], cwd=nested_repo2, check=True)

        # Change to board_path directory for testing
        original_cwd = os.getcwd()
        try:
            os.chdir(board_path)

            # Test repository detection
            repositories = patch_override._PatchOverride__find_repositories(board_path)

            # Should find 2 repositories
            assert len(repositories) == 2

            repo_paths = [repo[0] for repo in repositories]
            repo_names = [repo[1] for repo in repositories]

            assert nested_repo1 in repo_paths
            assert nested_repo2 in repo_paths

            assert "nested/repo1" in repo_names
            assert "nested/repo2" in repo_names
        finally:
            os.chdir(original_cwd)

    def test_po_new_get_modified_files(self):
        """Test __get_modified_files functionality including staged files."""
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Create a git repository with modified files
        board_path = os.path.join(self.vprojects_path, "test_board")
        subprocess.run(["git", "init"], cwd=board_path, check=True)

        # Create initial file
        initial_file = os.path.join(board_path, "test.txt")
        with open(initial_file, 'w', encoding='utf-8') as f:
            f.write("initial content")

        subprocess.run(["git", "add", "test.txt"], cwd=board_path, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=board_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=board_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=board_path, check=True)

        # Modify the file
        with open(initial_file, 'w', encoding='utf-8') as f:
            f.write("modified content")

        # Create and stage a new file
        staged_file = os.path.join(board_path, "staged.txt")
        with open(staged_file, 'w', encoding='utf-8') as f:
            f.write("staged content")
        subprocess.run(["git", "add", "staged.txt"], cwd=board_path, check=True)

        # Create new untracked file
        new_file = os.path.join(board_path, "new.txt")
        with open(new_file, 'w', encoding='utf-8') as f:
            f.write("new file content")

        # Test getting modified files
        modified_files = patch_override._PatchOverride__get_modified_files(board_path, "root")

        # Should find modified, staged, and new files
        assert len(modified_files) >= 3

        file_paths = [file[1] for file in modified_files]
        statuses = [file[2] for file in modified_files]

        assert "test.txt" in file_paths
        assert "staged.txt" in file_paths
        assert "new.txt" in file_paths

        # Check that staged file has appropriate status
        staged_index = file_paths.index("staged.txt")
        assert "(staged)" in statuses[staged_index]

    def test_po_new_create_patch_for_file(self):
        """Test __create_patch_for_file functionality."""
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Create a git repository in the current working directory
        original_cwd = os.getcwd()
        try:
            # Change to a temporary directory to test
            test_dir = tempfile.mkdtemp()
            os.chdir(test_dir)

            # Create initial file
            test_file = os.path.join(test_dir, "test.py")
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write("print('Hello')\n")

            subprocess.run(["git", "init"], cwd=test_dir, check=True)
            subprocess.run(["git", "add", "test.py"], cwd=test_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=test_dir, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=test_dir, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=test_dir, check=True)

            # Modify the file
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write("print('Hello')\nprint('Modified')\n")

            # Create PO directory structure
            board_path = os.path.join(self.vprojects_path, "test_board")
            po_path = os.path.join(board_path, "po", "po_test")
            patches_dir = os.path.join(po_path, "patches")
            os.makedirs(patches_dir, exist_ok=True)

            # Test creating patch
            result = patch_override._PatchOverride__create_patch_for_file("root", "test.py", patches_dir, force=True)
            assert result is True

            # Verify patch file was created
            patch_file = os.path.join(patches_dir, "root_test.py.patch")
            assert os.path.exists(patch_file)

            # Verify patch content
            with open(patch_file, 'r', encoding='utf-8') as f:
                patch_content = f.read()
            assert "print('Modified')" in patch_content

        finally:
            os.chdir(original_cwd)
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_po_new_create_override_for_file(self):
        """Test __create_override_for_file functionality."""
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Create a git repository with a file
        board_path = os.path.join(self.vprojects_path, "test_board")
        subprocess.run(["git", "init"], cwd=board_path, check=True)

        # Create a file
        test_file = os.path.join(board_path, "config.ini")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("debug=true\nport=8080\n")

        # Create PO directory structure
        po_path = os.path.join(board_path, "po", "po_test")
        overrides_dir = os.path.join(po_path, "overrides")
        os.makedirs(overrides_dir, exist_ok=True)

        # Change to board_path directory for testing
        original_cwd = os.getcwd()
        try:
            os.chdir(board_path)

            # Test creating override
            result = patch_override._PatchOverride__create_override_for_file("root", "config.ini", overrides_dir, board_path)
            assert result is True

            # Verify override file was created
            override_file = os.path.join(overrides_dir, "root", "config.ini")
            assert os.path.exists(override_file)

            # Verify file content
            with open(override_file, 'r', encoding='utf-8') as f:
                content = f.read()
            assert "debug=true" in content
            assert "port=8080" in content
        finally:
            os.chdir(original_cwd)

    def test_po_new_find_repo_path_by_name(self):
        """Test __find_repo_path_by_name functionality."""
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Create a git repository
        board_path = os.path.join(self.vprojects_path, "test_board")
        subproject_path = os.path.join(board_path, "subproject")
        os.makedirs(subproject_path)

        subprocess.run(["git", "init"], cwd=board_path, check=True)
        subprocess.run(["git", "init"], cwd=subproject_path, check=True)

        # Change to board_path directory for testing
        original_cwd = os.getcwd()
        try:
            os.chdir(board_path)

            # Test finding root repository
            result = patch_override._PatchOverride__find_repo_path_by_name("root")
            assert result == board_path

            # Test finding subproject repository
            result = patch_override._PatchOverride__find_repo_path_by_name("subproject")
            assert result == subproject_path

            # Test finding non-existent repository
            result = patch_override._PatchOverride__find_repo_path_by_name("nonexistent")
            assert result is None
        finally:
            os.chdir(original_cwd)

    def test_po_new_confirm_creation(self):
        """Test __confirm_creation functionality."""
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Test confirmation (this would normally require user input)
        # For testing, we'll just verify the method exists and can be called
        # po_name = "po_test"
        # po_path = os.path.join(self.vprojects_path, "test_board", "po", po_name)
        # board_path = os.path.join(self.vprojects_path, "test_board")

        # The method should exist and be callable
        assert hasattr(patch_override, '_PatchOverride__confirm_creation')
        assert callable(patch_override._PatchOverride__confirm_creation)

    def test_po_new_interactive_file_selection(self):
        """Test __interactive_file_selection functionality."""
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Create a git repository with modified files
        board_path = os.path.join(self.vprojects_path, "test_board")
        subprocess.run(["git", "init"], cwd=board_path, check=True)

        # Create and modify a file
        test_file = os.path.join(board_path, "test.py")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("print('Hello')\n")

        subprocess.run(["git", "add", "test.py"], cwd=board_path, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=board_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=board_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=board_path, check=True)

        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("print('Modified')\n")

        # Create PO directory structure
        po_path = os.path.join(board_path, "po", "po_test")
        os.makedirs(po_path, exist_ok=True)

        # Test interactive file selection (this would normally require user input)
        # For testing, we'll just verify the method exists and can be called
        assert hasattr(patch_override, '_PatchOverride__interactive_file_selection')
        assert callable(patch_override._PatchOverride__interactive_file_selection)

    def test_po_new_process_selected_files(self):
        """Test __process_selected_files functionality."""
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Create a git repository with a file
        board_path = os.path.join(self.vprojects_path, "test_board")
        subprocess.run(["git", "init"], cwd=board_path, check=True)

        test_file = os.path.join(board_path, "test.py")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("print('Hello')\n")

        subprocess.run(["git", "add", "test.py"], cwd=board_path, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=board_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=board_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=board_path, check=True)

        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("print('Modified')\n")

        # Create PO directory structure
        po_path = os.path.join(board_path, "po", "po_test")
        os.makedirs(po_path, exist_ok=True)

        # Create selected files list
        # selected_files = [("root", "test.py", "M ")]

        # Test processing selected files (this would normally require user input)
        # For testing, we'll just verify the method exists and can be called
        assert hasattr(patch_override, '_PatchOverride__process_selected_files')
        assert callable(patch_override._PatchOverride__process_selected_files)

    def test_po_new_invalid_project(self):
        """Test po_new with invalid project name."""
        # Create PatchOverride instance
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Try to create PO for invalid project
        result = patch_override.po_new("invalid_project", "test_po", force=True)
        assert result is False

    def test_po_new_missing_board_name(self):
        """Test po_new with project that has no board_name."""
        # Create PatchOverride instance with project info missing board_name
        all_projects_info = {
            "test_project_no_board": {
                "PROJECT_PO_CONFIG": "po_test01"
            }
        }
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Try to create PO for project without board_name
        result = patch_override.po_new("test_project_no_board", "test_po", force=True)
        assert result is False

    def test_po_new_invalid_name_no_po_prefix(self):
        """Test po_new with po_name that doesn't start with 'po'."""
        # Create PatchOverride instance
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Try to create PO with invalid name (doesn't start with 'po')
        result = patch_override.po_new("test_project", "invalid_name", force=True)
        assert result is False

    def test_po_new_invalid_name_uppercase(self):
        """Test po_new with po_name containing uppercase letters."""
        # Create PatchOverride instance
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Try to create PO with invalid name (contains uppercase)
        result = patch_override.po_new("test_project", "po_Test", force=True)
        assert result is False

    def test_po_new_invalid_name_special_chars(self):
        """Test po_new with po_name containing special characters."""
        # Create PatchOverride instance
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Try to create PO with invalid name (contains special characters)
        result = patch_override.po_new("test_project", "po-test", force=True)
        assert result is False

    def test_po_new_valid_names(self):
        """Test po_new with various valid po_name formats."""
        # Create PatchOverride instance
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Test various valid names
        valid_names = [
            "po_test",
            "po123",
            "po_test_123",
            "po_",
            "po123test"
        ]

        for po_name in valid_names:
            result = patch_override.po_new("test_project", po_name, force=True)
            assert result is True, f"Failed for valid name: {po_name}"

            # Verify directory was created
            board_path = os.path.join(self.vprojects_path, "test_board")
            po_path = os.path.join(board_path, "po", po_name)
            assert os.path.exists(po_path), f"Directory not created for: {po_name}"

    def test_po_del_invalid_po_name(self):
        """Test po_del with invalid PO name."""
        result = self.patch_override.po_del("test_project", "invalid_po", force=True)
        assert result is False

    def test_po_del_nonexistent_po(self):
        """Test po_del with non-existent PO."""
        result = self.patch_override.po_del("test_project", "po_nonexistent", force=True)
        assert result is False

    def test_po_del_success(self):
        """Test successful po_del operation."""
        # Remove existing po_test01 if it exists
        test_po_name = "po_test01"
        test_po_path = os.path.join(self.vprojects_path, "test_board", "po", test_po_name)
        if os.path.exists(test_po_path):
            shutil.rmtree(test_po_path)

        # Create a fresh test PO directory
        os.makedirs(test_po_path)
        os.makedirs(os.path.join(test_po_path, "patches"))
        os.makedirs(os.path.join(test_po_path, "overrides"))

        # Create a test file in the PO
        test_file = os.path.join(test_po_path, "test.txt")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("test content")

        # Verify PO exists
        assert os.path.exists(test_po_path)

        # Execute po_del with force=True to skip confirmation
        result = self.patch_override.po_del("test_project", test_po_name, force=True)

        # Verify PO was deleted
        assert result is True
        assert not os.path.exists(test_po_path)

        # Verify PO was removed from config
        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(os.path.join(self.vprojects_path, "test_board", "board.ini"), encoding="utf-8")

        # Check that po_test01 was removed from test_project config
        updated_config = config.get("test_project", "PROJECT_PO_CONFIG")
        assert "po_test01" not in updated_config
        assert "po_test02" in updated_config  # Other POs should remain
        assert "-po_test03" in updated_config

    def test_po_del_with_file_exclusions(self):
        """Test po_del with PO that has file exclusions."""
        # Remove existing po_test03 if it exists
        test_po_name = "po_test03"
        test_po_path = os.path.join(self.vprojects_path, "test_board", "po", test_po_name)
        if os.path.exists(test_po_path):
            shutil.rmtree(test_po_path)

        # Create a fresh test PO directory
        os.makedirs(test_po_path)

        # Execute po_del
        result = self.patch_override.po_del("test_project", test_po_name, force=True)

        # Verify PO was deleted
        assert result is True
        assert not os.path.exists(test_po_path)

        # Verify PO was removed from config (including the exclusion)
        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(os.path.join(self.vprojects_path, "test_board", "board.ini"), encoding="utf-8")

        updated_config = config.get("test_project", "PROJECT_PO_CONFIG")
        assert "-po_test03" not in updated_config
        assert "po_test01" in updated_config
        assert "po_test02" in updated_config

    def test_po_del_removes_empty_po_directory(self):
        """Test that po_del removes the po directory if it becomes empty."""
        # Remove all existing POs to make po directory empty
        po_dir = os.path.join(self.vprojects_path, "test_board", "po")
        for item in os.listdir(po_dir):
            item_path = os.path.join(po_dir, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)

        # Create only one PO
        test_po_name = "po_test01"
        test_po_path = os.path.join(po_dir, test_po_name)
        os.makedirs(test_po_path)

        # Verify po directory exists
        assert os.path.exists(po_dir)

        # Execute po_del
        result = self.patch_override.po_del("test_project", test_po_name, force=True)

        # Verify PO was deleted and po directory was removed
        assert result is True
        assert not os.path.exists(test_po_path)
        assert not os.path.exists(po_dir)

    def test_remove_po_from_config_string(self):
        """Test the helper method for removing PO from config string."""
        # Test removing a simple PO
        config = "po_test01 po_test02"
        result = self.patch_override._PatchOverride__remove_po_from_config_string(config, "po_test01")
        assert result == "po_test02"

        # Test removing an excluded PO
        config = "po_test01 -po_test02"
        result = self.patch_override._PatchOverride__remove_po_from_config_string(config, "po_test02")
        assert result == "po_test01"

        # Test removing PO with file exclusions
        config = "po_test01 -po_test02[file1.c file2.c]"
        result = self.patch_override._PatchOverride__remove_po_from_config_string(config, "po_test02")
        assert result == "po_test01"

        # Test removing non-existent PO
        config = "po_test01 po_test02"
        result = self.patch_override._PatchOverride__remove_po_from_config_string(config, "po_test03")
        assert result == "po_test01 po_test02"

        # Test empty config
        result = self.patch_override._PatchOverride__remove_po_from_config_string("", "po_test01")
        assert result == ""

if __name__ == "__main__":
    # Run tests if script is executed directly
    pytest.main([__file__, "-v"])
