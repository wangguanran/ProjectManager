"""
Utility functions collection.
"""

import os
import sys
import time

import toml


def path_from_root(*args):
    """
    Constructs an absolute path from path components relative to the current working directory.

    Args:
        *args: Variable length argument list for path components.

    Returns:
        str: The absolute path.
    """
    return os.path.join(os.getcwd(), *args)


def get_filename(prefix, suffix, path):
    """
    Generates a unique filename with a timestamp.

    Args:
        prefix (str): The prefix for the filename.
        suffix (str): The suffix for the filename.
        path (str): The directory where the file will be located.

    Returns:
        str: The full path for the new file.
    """
    path = path_from_root(path)
    if not os.path.exists(path):
        os.makedirs(path)
    date_str = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(path, "".join((prefix, date_str, suffix)))


def get_version():
    """
    Retrieves the project version from pyproject.toml.

    It is compatible with both source execution and PyInstaller-packed applications.

    Returns:
        str: The project version, or "0.0.0-dev" if not found.
    """
    try:
        # Compatible with PyInstaller and source code execution
        if hasattr(sys, "_MEIPASS"):
            base_dir = getattr(sys, "_MEIPASS", None)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        # Handle None case for base_dir
        if base_dir is None:
            return "0.0.0-dev"

        pyproject_path = os.path.join(base_dir, "pyproject.toml")
        if not os.path.exists(pyproject_path):
            pyproject_path = os.path.join(base_dir, "../pyproject.toml")
        data = toml.load(pyproject_path)
        return data["project"]["version"]
    except (OSError, KeyError, toml.TomlDecodeError):
        return "0.0.0-dev"


def list_file_path(root, max_depth=0xFF, list_dir=False, only_dir=False):
    """
    Recursively lists file or directory paths in a directory up to max_depth.

    Args:
        root (str): The directory path to search.
        max_depth (int): The maximum recursion depth.
        list_dir (bool): If True, include directories in the result.
        only_dir (bool): If True, only include directories in the result.

    Yields:
        str: The next file or directory path found.
    """
    root = path_from_root(root)
    root_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        cur_depth = dirpath.rstrip(os.sep).count(os.sep) - root_depth
        if cur_depth >= max_depth:
            dirnames[:] = []  # Stop recursing further
            # Still yield files at current depth if not only_dir
            if not only_dir:
                for f in filenames:
                    yield os.path.join(dirpath, f)
            continue
        if list_dir or only_dir:
            for d in dirnames:
                yield os.path.join(dirpath, d)
        if not only_dir:
            for f in filenames:
                yield os.path.join(dirpath, f)
