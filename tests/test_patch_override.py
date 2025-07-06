"""
Tests for patch and override operations.
"""
import os
import sys
import tempfile
import shutil
import subprocess
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

def load_patch_override():
    """Dynamically load the PatchOverride module for testing."""
    # Add the project root to Python path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Now import the module normally
    from src.plugins.patch_override import PatchOverride
    return PatchOverride

class TestPatchOverride:
    """Test class for patch and override operations."""

    def setup_method(self):
        """Set up test environment before each test."""
        self.temp_dir = tempfile.mkdtemp()
        print(f"Created temporary directory: {self.temp_dir}")
        self.vprojects_path = os.path.join(self.temp_dir, "vprojects")
        self.test_repo_path = os.path.join(self.temp_dir, "test_repo")

        # Create vprojects directory structure
        os.makedirs(self.vprojects_path)

        # Create test git repository
        self._create_test_git_repo()

        # Create test project structure
        self._create_test_project_structure()

        # Load PatchOverride class
        self.PatchOverride = load_patch_override()

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
            patch_override = self.PatchOverride(self.vprojects_path, all_projects_info)

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
            patch_override = self.PatchOverride(self.vprojects_path, all_projects_info)

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
            patch_override = self.PatchOverride(self.vprojects_path, all_projects_info)

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
            patch_override = self.PatchOverride(self.vprojects_path, all_projects_info)

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

            patch_override = self.PatchOverride(self.vprojects_path, all_projects_info)

            # Apply po_apply
            result = patch_override.po_apply("test_project_no_config")

            # Should return True (no config means success)
            assert result is True

        finally:
            os.chdir(original_cwd)

if __name__ == "__main__":
    # Run tests if script is executed directly
    pytest.main([__file__, "-v"])
