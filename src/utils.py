"""
Utility functions collection.
"""

import os
import shutil
import time
import sys
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


def organize_files(path, prefix):
    """
    Organizes files into subdirectories based on their date.

    Args:
        path (str): The path of the directory to organize.
        prefix (str): The prefix to use for the subdirectories.
    """
    if os.path.exists(path):
        file_list = os.listdir(path)
        for file in file_list:
            file_fullpath = os.path.join(path, file)
            if os.path.isfile(file_fullpath):
                # Extract date from filename (second part after underscore)
                # Expected pattern: prefix_date_rest
                parts = file.split("_")
                if len(parts) >= 2 and file.startswith(prefix):
                    # File matches expected pattern: prefix_date_rest
                    log_data = parts[1]
                else:
                    # If no underscore pattern or doesn't match expected pattern, use "other" as category
                    log_data = "other"
                log_dir = os.path.join(path, prefix + log_data)
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                dest_file = os.path.join(log_dir, os.path.basename(file_fullpath))
                if os.path.exists(dest_file):
                    os.remove(dest_file)
                shutil.move(file_fullpath, log_dir)


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
