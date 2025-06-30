"""
Tests for utils functions.
"""
import os
import sys
import importlib.util
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

def load_utils():
    """Dynamically load the utils module from src/utils.py for testing."""
    utils_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/utils.py"))
    spec = importlib.util.spec_from_file_location("utils", utils_path)
    utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(utils)
    return utils

def test_path_from_root(tmp_path, monkeypatch):
    """Test path_from_root."""
    utils = load_utils()
    monkeypatch.chdir(tmp_path)
    assert utils.path_from_root("a", "b") == os.path.join(str(tmp_path), "a", "b")

def test_get_filename(tmp_path, monkeypatch):
    """Test get_filename."""
    utils = load_utils()
    monkeypatch.chdir(tmp_path)
    fn = utils.get_filename("pre_", ".suf", "logdir")
    assert fn.startswith(os.path.join(str(tmp_path), "logdir", "pre_"))
    assert fn.endswith(".suf")
    assert os.path.exists(os.path.dirname(fn))

def test_organize_files(tmp_path, monkeypatch):
    """Test organize_files."""
    utils = load_utils()
    monkeypatch.chdir(tmp_path)
    logdir = tmp_path / "log"
    logdir.mkdir()
    # Create multiple files
    files = []
    for i in range(3):
        f = logdir / f"LOG_20220101_{i}.txt"
        f.write_text("test")
        files.append(f)
    utils.organize_files(str(logdir), "LOG_")
    # Check if files were moved to subdirectories
    for f in files:
        log_data = f.name.split("_")[1]
        subdir = logdir / ("LOG_" + log_data)
        assert subdir.exists()
        dest_file = subdir / f.name
        assert dest_file.exists()

def test_get_version(tmp_path, monkeypatch):
    """Test get_version."""
    utils = load_utils()
    # Create pyproject.toml
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[project]
version = "1.2.3"
""")
    monkeypatch.chdir(tmp_path)
    old_file = utils.__file__
    utils.__file__ = str(pyproject)
    try:
        assert utils.get_version() == "1.2.3"
    finally:
        utils.__file__ = old_file

def test_list_file_path(tmp_path, monkeypatch):
    """Test list_file_path."""
    utils = load_utils()
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
    files = list(utils.list_file_path("d1"))
    assert file1 in map(os.path.abspath, files) or str(file1) in files
    assert file2 in map(os.path.abspath, files) or str(file2) in files
    # List only directories
    dirs = list(utils.list_file_path("d1", list_dir=True, only_dir=True))
    assert dir2 in map(os.path.abspath, dirs) or str(dir2) in dirs
    # List both files and directories
    all_items = list(utils.list_file_path("d1", list_dir=True))
    assert any(str(file1) in x or str(file2) in x for x in all_items)
    assert any(str(dir2) in x for x in all_items)
    # Test max_depth
    shallow = list(utils.list_file_path("d1", max_depth=1))
    # file2 (d2/f2.txt) should not appear in shallow
    assert not any(str(file2) in x for x in shallow)
