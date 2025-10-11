"""Utility helpers shared across the project."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Union

import toml

PathLike = Union[str, os.PathLike[str]]


def path_from_root(*parts: PathLike) -> str:
    """Join ``parts`` to the current working directory and return the path as ``str``.

    ``path_from_root`` behaves like :class:`pathlib.Path`'s ``joinpath`` which means that if
    any argument is an absolute path it will replace the accumulated result. This keeps the
    helper intuitive while still allowing callers to pass pre-built :class:`Path` objects.
    """

    cwd = Path.cwd()
    if not parts:
        return str(cwd)

    joined = cwd.joinpath(*(Path(p) for p in parts))
    return str(joined)


def get_filename(prefix: str, suffix: str, directory: PathLike) -> str:
    """Return an absolute filename constructed from ``prefix`` and ``suffix``.

    The filename is generated under ``directory`` (relative to the current working directory)
    and suffixed with a timestamp so repeated calls do not collide.
    """

    target_dir = Path(path_from_root(directory))
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return str(target_dir / f"{prefix}{timestamp}{suffix}")


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
