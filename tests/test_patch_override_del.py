"""
Tests for patch and override delete operations.
"""

# pylint: disable=attribute-defined-outside-init, import-outside-toplevel, too-many-public-methods, protected-access
import os
import shutil
import configparser
import pytest
from test_patch_override_base import BasePatchOverrideTest


class TestPatchOverrideDel(BasePatchOverrideTest):
    """Test class for patch and override delete operations."""

    def test_basic_functionality(self):
        """Test basic functionality - implementation of abstract method."""
        # This is a placeholder for the abstract method
        assert True

    def test_po_del_invalid_po_name(self):
        """Test po_del with invalid PO name."""
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Test with invalid PO name
        result = patch_override.po_del("test_project", "invalid_name", force=True)
        assert result is False

    def test_po_del_nonexistent_po(self):
        """Test po_del with non-existent PO."""
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Try to delete non-existent PO
        result = patch_override.po_del("test_project", "po_nonexistent", force=True)
        assert result is False

    def test_po_del_ini_file_error(self):
        """Test po_del when INI file operations fail."""
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Create a PO to delete
        test_po_name = "po_test_ini_error"
        test_po_path = os.path.join(
            self.vprojects_path, "test_board", "po", test_po_name
        )
        os.makedirs(test_po_path, exist_ok=True)
        os.makedirs(os.path.join(test_po_path, "patches"), exist_ok=True)
        os.makedirs(os.path.join(test_po_path, "overrides"), exist_ok=True)

        # Make the INI file read-only to cause write failure
        ini_file = os.path.join(self.vprojects_path, "test_board", "board.ini")
        original_mode = os.stat(ini_file).st_mode
        os.chmod(ini_file, 0o444)  # Read-only

        try:
            # Try to delete PO (should fail due to INI file write error)
            result = patch_override.po_del("test_project", test_po_name, force=True)
            assert result is False
        finally:
            # Restore file permissions
            os.chmod(ini_file, original_mode)
            # Clean up
            if os.path.exists(test_po_path):
                shutil.rmtree(test_po_path)

    def test_po_del_with_multiple_projects(self):
        """Test po_del when PO is used by multiple projects."""
        # Create multiple projects using the same PO
        all_projects_info = {
            "test_project1": {
                "board_name": "test_board",
                "PROJECT_PO_CONFIG": "po_shared",
            },
            "test_project2": {
                "board_name": "test_board",
                "PROJECT_PO_CONFIG": "po_shared po_test01",
            },
        }

        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Create a shared PO
        shared_po_path = os.path.join(
            self.vprojects_path, "test_board", "po", "po_shared"
        )
        os.makedirs(shared_po_path, exist_ok=True)
        os.makedirs(os.path.join(shared_po_path, "patches"), exist_ok=True)
        os.makedirs(os.path.join(shared_po_path, "overrides"), exist_ok=True)

        # Update board.ini to include both projects
        board_ini = os.path.join(self.vprojects_path, "test_board", "board.ini")
        with open(board_ini, "w", encoding="utf-8") as f:
            f.write(
                """[test_project1]
board_name = test_board
PROJECT_PO_CONFIG = po_shared

[test_project2]
board_name = test_board
PROJECT_PO_CONFIG = po_shared po_test01
"""
            )

        # Delete the shared PO
        result = patch_override.po_del("test_project1", "po_shared", force=True)
        assert result is True

        # Verify PO was deleted
        assert not os.path.exists(shared_po_path)

        # Verify PO was removed from both project configs
        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(board_ini, encoding="utf-8")

        config1 = config.get("test_project1", "PROJECT_PO_CONFIG")
        config2 = config.get("test_project2", "PROJECT_PO_CONFIG")

        assert "po_shared" not in config1
        assert "po_shared" not in config2
        assert "po_test01" in config2  # Other POs should remain

    def test_po_del_with_empty_po_directory(self):
        """Test po_del when PO directory becomes empty after deletion."""
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Create a PO to delete
        test_po_name = "po_test_empty"
        test_po_path = os.path.join(
            self.vprojects_path, "test_board", "po", test_po_name
        )
        os.makedirs(test_po_path, exist_ok=True)
        os.makedirs(os.path.join(test_po_path, "patches"), exist_ok=True)
        os.makedirs(os.path.join(test_po_path, "overrides"), exist_ok=True)

        # Verify PO exists
        assert os.path.exists(test_po_path)

        # Delete the PO
        result = patch_override.po_del("test_project", test_po_name, force=True)
        assert result is True

        # Verify PO was deleted
        assert not os.path.exists(test_po_path)

        # Verify po directory still exists (it should not be empty due to other POs)
        po_dir = os.path.join(self.vprojects_path, "test_board", "po")
        assert os.path.exists(po_dir)

    def test_po_del_with_os_error(self):
        """Test po_del with OS error during directory deletion."""
        all_projects_info = self._load_all_projects_info()
        patch_override = self.patch_override_cls(self.vprojects_path, all_projects_info)

        # Create a PO to delete
        test_po_name = "po_test_os_error"
        test_po_path = os.path.join(
            self.vprojects_path, "test_board", "po", test_po_name
        )
        os.makedirs(test_po_path, exist_ok=True)
        os.makedirs(os.path.join(test_po_path, "patches"), exist_ok=True)
        os.makedirs(os.path.join(test_po_path, "overrides"), exist_ok=True)

        # Create a read-only file inside the PO to cause deletion error
        readonly_file = os.path.join(test_po_path, "readonly_file.txt")
        with open(readonly_file, "w", encoding="utf-8") as f:
            f.write("test")
        os.chmod(readonly_file, 0o444)  # Read-only

        try:
            # Try to delete PO (should succeed because shutil.rmtree can handle read-only files)
            result = patch_override.po_del("test_project", test_po_name, force=True)
            assert result is True
        finally:
            # Clean up
            if os.path.exists(readonly_file):
                os.chmod(readonly_file, 0o644)
            if os.path.exists(test_po_path):
                shutil.rmtree(test_po_path, ignore_errors=True)


if __name__ == "__main__":
    # Run tests if script is executed directly
    pytest.main([__file__, "-v"])
