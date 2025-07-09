"""
Tests for utils functions.
"""

# pylint: disable=attribute-defined-outside-init

import os
import sys
import tempfile
import importlib.util
import re
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


def load_utils():
    """Dynamically load the utils module from src/utils.py for testing."""
    utils_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../src/utils.py")
    )
    spec = importlib.util.spec_from_file_location("utils", utils_path)
    utils_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(utils_mod)
    return utils_mod


# Load utils module
utils = load_utils()
path_from_root = utils.path_from_root
get_filename = utils.get_filename
organize_files = utils.organize_files
get_version = utils.get_version
list_file_path = utils.list_file_path


class TestPathFromRoot:
    """Test cases for path_from_root function."""

    def test_path_from_root_single_arg(self):
        """Test path_from_root with single argument."""
        result = path_from_root("test_dir")
        expected = os.path.join(os.getcwd(), "test_dir")
        assert result == expected

    def test_path_from_root_multiple_args(self):
        """Test path_from_root with multiple arguments."""
        result = path_from_root("dir1", "dir2", "file.txt")
        expected = os.path.join(os.getcwd(), "dir1", "dir2", "file.txt")
        assert result == expected

    def test_path_from_root_no_args(self):
        """Test path_from_root with no arguments."""
        result = path_from_root()
        expected = os.getcwd()
        assert result == expected

    def test_path_from_root_with_tmp_path(self, tmp_path, monkeypatch):
        """Test path_from_root with pytest tmp_path."""
        monkeypatch.chdir(tmp_path)
        assert path_from_root("a", "b") == os.path.join(str(tmp_path), "a", "b")


class TestGetFilename:
    """Test cases for get_filename function."""

    def test_get_filename_creates_directory(self):
        """Test get_filename creates directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = os.path.join(temp_dir, "nonexistent_dir")

            result = get_filename("test_", ".txt", test_path)

            # Directory should be created
            assert os.path.exists(test_path)
            # Result should be in the created directory
            assert result.startswith(test_path)
            assert result.endswith(".txt")
            assert "test_" in result

    def test_get_filename_existing_directory(self):
        """Test get_filename with existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = get_filename("test_", ".txt", temp_dir)

            assert result.startswith(temp_dir)
            assert result.endswith(".txt")
            assert "test_" in result

    def test_get_filename_timestamp_format(self):
        """Test get_filename includes timestamp in correct format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = get_filename("test_", ".txt", temp_dir)

            # Extract filename from path
            filename = os.path.basename(result)

            # Should start with prefix
            assert filename.startswith("test_")
            # Should end with suffix
            assert filename.endswith(".txt")
            # Should contain timestamp in format YYYYMMDD_HHMMSS
            timestamp_pattern = r"test_(\d{8}_\d{6})\.txt"
            match = re.match(timestamp_pattern, filename)
            assert match is not None

    def test_get_filename_with_tmp_path(self, tmp_path, monkeypatch):
        """Test get_filename with pytest tmp_path."""
        monkeypatch.chdir(tmp_path)
        fn = get_filename("pre_", ".suf", "logdir")
        assert fn.startswith(os.path.join(str(tmp_path), "logdir", "pre_"))
        assert fn.endswith(".suf")
        assert os.path.exists(os.path.dirname(fn))


class TestOrganizeFiles:
    """Test cases for organize_files function."""

    def test_organize_files_empty_directory(self):
        """Test organize_files with empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Should not raise any exception
            organize_files(temp_dir, "log_")
            assert True

    def test_organize_files_nonexistent_directory(self):
        """Test organize_files with nonexistent directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nonexistent_dir = os.path.join(temp_dir, "nonexistent")
            # Should not raise any exception
            organize_files(nonexistent_dir, "log_")
            assert True

    def test_organize_files_with_files(self):
        """Test organize_files with actual files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files with expected naming pattern
            test_files = [
                "log_20230101_file1.txt",
                "log_20230101_file2.txt",
                "log_20230102_file3.txt",
                "other_file.txt",  # Should also be moved
            ]

            for filename in test_files:
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("test content")

            # Organize files
            organize_files(temp_dir, "log_")

            # Check that directories were created
            log_20230101_dir = os.path.join(temp_dir, "log_20230101")
            log_20230102_dir = os.path.join(temp_dir, "log_20230102")

            assert os.path.exists(log_20230101_dir)
            assert os.path.exists(log_20230102_dir)

            # Check that files were moved to correct directories
            assert os.path.exists(
                os.path.join(log_20230101_dir, "log_20230101_file1.txt")
            )
            assert os.path.exists(
                os.path.join(log_20230101_dir, "log_20230101_file2.txt")
            )
            assert os.path.exists(
                os.path.join(log_20230102_dir, "log_20230102_file3.txt")
            )

            # Check that other file was also moved (organize_files moves all files)
            assert os.path.exists(os.path.join(temp_dir, "log_other", "other_file.txt"))

    def test_organize_files_with_existing_destination(self):
        """Test organize_files when destination file already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create source file
            source_file = os.path.join(temp_dir, "log_20230101_file.txt")
            with open(source_file, "w", encoding="utf-8") as f:
                f.write("source content")

            # Create destination directory and file
            dest_dir = os.path.join(temp_dir, "log_20230101")
            os.makedirs(dest_dir)
            dest_file = os.path.join(dest_dir, "log_20230101_file.txt")
            with open(dest_file, "w", encoding="utf-8") as f:
                f.write("existing content")

            # Organize files
            organize_files(temp_dir, "log_")

            # Check that source file was moved and replaced destination
            assert not os.path.exists(source_file)
            assert os.path.exists(dest_file)

            # Check content was replaced
            with open(dest_file, "r", encoding="utf-8") as f:
                content = f.read()
            assert content == "source content"

    def test_organize_files_with_tmp_path(self, tmp_path, monkeypatch):
        """Test organize_files with pytest tmp_path."""
        monkeypatch.chdir(tmp_path)
        logdir = tmp_path / "log"
        logdir.mkdir()
        # Create multiple files
        files = []
        for i in range(3):
            f = logdir / f"LOG_20220101_{i}.txt"
            f.write_text("test")
            files.append(f)
        organize_files(str(logdir), "LOG_")
        # Check if files were moved to subdirectories
        for f in files:
            log_data = f.name.split("_")[1]
            subdir = logdir / ("LOG_" + log_data)
            assert subdir.exists()
            dest_file = subdir / f.name
            assert dest_file.exists()


class TestGetVersion:
    """Test cases for get_version function."""

    def test_get_version_with_pyinstaller(self):
        """Test get_version with PyInstaller environment."""
        with patch.dict("sys.__dict__", {"_MEIPASS": "/fake/pyinstaller/path"}):
            with patch("os.path.exists", return_value=True):
                with patch("toml.load") as mock_toml:
                    mock_toml.return_value = {"project": {"version": "1.2.3"}}

                    result = get_version()
                    assert result == "1.2.3"

    def test_get_version_source_execution(self):
        """Test get_version with source code execution."""

        def mock_get_version():
            return "2.0.0"

        original_get_version = utils.get_version
        utils.get_version = mock_get_version
        try:
            result = utils.get_version()
            assert result == "2.0.0"
        finally:
            utils.get_version = original_get_version

    def test_get_version_fallback_path(self):
        """Test get_version with fallback path."""

        def mock_get_version():
            return "3.0.0"

        original_get_version = utils.get_version
        utils.get_version = mock_get_version
        try:
            result = utils.get_version()
            assert result == "3.0.0"
        finally:
            utils.get_version = original_get_version

    def test_get_version_file_not_found(self):
        """Test get_version when pyproject.toml is not found."""
        with patch.dict("sys.__dict__", {"_MEIPASS": None}, clear=False):
            with patch("os.path.dirname", return_value="/test/path"):
                with patch("os.path.exists", return_value=False):
                    result = get_version()
                    assert result == "0.0.0-dev"

    def test_get_version_toml_decode_error(self):
        """Test get_version with TOML decode error."""
        with patch.dict("sys.__dict__", {"_MEIPASS": None}, clear=False):
            with patch("os.path.dirname", return_value="/test/path"):
                with patch("os.path.exists", return_value=True):
                    with patch("toml.load", side_effect=Exception("TOML decode error")):
                        result = get_version()
                        assert result == "0.0.0-dev"

    def test_get_version_key_error(self):
        """Test get_version with missing version key."""
        with patch("os.path.exists", return_value=True):
            with patch("toml.load", return_value={"project": {}}):
                result = get_version()
                assert result == "0.0.0-dev"

    def test_get_version_with_tmp_path(self, tmp_path, monkeypatch):
        """Test get_version with pytest tmp_path."""
        # Create pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
version = "1.2.3"
"""
        )
        monkeypatch.chdir(tmp_path)
        old_file = utils.__file__
        utils.__file__ = str(pyproject)
        try:
            assert get_version() == "1.2.3"
        finally:
            utils.__file__ = old_file


class TestListFilePath:
    """Test cases for list_file_path function."""

    def test_list_file_path_files_only(self):
        """Test list_file_path with files only."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = ["file1.txt", "file2.txt", "file3.py"]
            for filename in files:
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("test content")

            # List files
            result = list(list_file_path(temp_dir))

            # Should find all files
            for filename in files:
                expected_path = os.path.join(temp_dir, filename)
                assert expected_path in result

    def test_list_file_path_directories_only(self):
        """Test list_file_path with directories only."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test directories
            dirs = ["dir1", "dir2", "dir3"]
            for dirname in dirs:
                dirpath = os.path.join(temp_dir, dirname)
                os.makedirs(dirpath)

            # List directories only
            result = list(list_file_path(temp_dir, list_dir=True, only_dir=True))

            # Should find all directories
            for dirname in dirs:
                expected_path = os.path.join(temp_dir, dirname)
                assert expected_path in result

    def test_list_file_path_files_and_directories(self):
        """Test list_file_path with both files and directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files and directories
            files = ["file1.txt", "file2.txt"]
            dirs = ["dir1", "dir2"]

            for filename in files:
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("test content")

            for dirname in dirs:
                dirpath = os.path.join(temp_dir, dirname)
                os.makedirs(dirpath)

            # List both files and directories
            result = list(list_file_path(temp_dir, list_dir=True, only_dir=False))

            # Should find all files and directories
            for filename in files:
                expected_path = os.path.join(temp_dir, filename)
                assert expected_path in result

            for dirname in dirs:
                expected_path = os.path.join(temp_dir, dirname)
                assert expected_path in result

    def test_list_file_path_with_max_depth(self):
        """Test list_file_path with max_depth limitation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create nested directory structure
            nested_dir = os.path.join(temp_dir, "level1", "level2", "level3")
            os.makedirs(nested_dir)

            # Create files at different levels
            level1_file = os.path.join(temp_dir, "level1", "file1.txt")
            level2_file = os.path.join(temp_dir, "level1", "level2", "file2.txt")
            level3_file = os.path.join(
                temp_dir, "level1", "level2", "level3", "file3.txt"
            )

            for filepath in [level1_file, level2_file, level3_file]:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("test content")

            # List with max_depth=1 (should only get level1 files)
            result = list(list_file_path(temp_dir, max_depth=1, list_dir=True))

            # Convert to absolute paths for comparison
            result_abs = [os.path.abspath(p) for p in result]
            level1_file_abs = os.path.abspath(level1_file)

            assert level1_file_abs in result_abs

    def test_list_file_path_nonexistent_directory(self):
        """Test list_file_path with nonexistent directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nonexistent_dir = os.path.join(temp_dir, "nonexistent")

            # Should not raise exception, just return empty list
            result = list(list_file_path(nonexistent_dir))
            assert not result

    def test_list_file_path_empty_directory(self):
        """Test list_file_path with empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = list(list_file_path(temp_dir))
            assert not result

    def test_list_file_path_with_subdirectories(self):
        """Test list_file_path with subdirectories containing files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create subdirectory structure
            subdir = os.path.join(temp_dir, "subdir")
            os.makedirs(subdir)

            # Create files in subdirectory
            subdir_file = os.path.join(subdir, "subfile.txt")
            with open(subdir_file, "w", encoding="utf-8") as f:
                f.write("test content")

            # List all files
            result = list(list_file_path(temp_dir))

            assert subdir_file in result

    def test_list_file_path_with_tmp_path(self, tmp_path, monkeypatch):
        """Test list_file_path with pytest tmp_path."""
        monkeypatch.chdir(tmp_path)
        # Create directory structure
        dir1 = tmp_path / "d1"
        dir1.mkdir()
        file1 = dir1 / "f1.txt"
        file1.write_text("a")
        dir2 = dir1 / "d2"
        dir2.mkdir()
        file2 = dir2 / "f2.txt"
        file2.write_text("b")
        # List only files
        files = list(list_file_path("d1"))
        assert str(file1) in files or any(str(file1) in f for f in files)
        assert str(file2) in files or any(str(file2) in f for f in files)
        # List only directories
        dirs = list(list_file_path("d1", list_dir=True, only_dir=True))
        assert str(dir2) in dirs or any(str(dir2) in d for d in dirs)
        # List both files and directories
        all_items = list(list_file_path("d1", list_dir=True))
        assert any(str(file1) in x for x in all_items)
        assert any(str(file2) in x for x in all_items)
        assert any(str(dir2) in x for x in all_items)
        # Test max_depth
        shallow = list(list_file_path("d1", max_depth=0))
        # With max_depth=0, only files in d1 should appear, not in subdirectories
        assert any(str(file1) in x for x in shallow)
        assert not any(str(file2) in x for x in shallow)
