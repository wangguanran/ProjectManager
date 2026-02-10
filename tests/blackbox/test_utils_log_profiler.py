"""Blackbox tests for utils/log/profiler."""

from __future__ import annotations

import builtins
import os
import re
from pathlib import Path

from src.profiler import func_cprofile
from src.utils import get_filename, get_version, list_file_path

from .conftest import run_cli


def test_util_001_version_matches_pyproject(workspace_a: Path) -> None:
    assert re.fullmatch(r"0\.0\.11(\+g[0-9a-f]{7,})?", get_version())


def test_util_002_version_fallback(tmp_path: Path) -> None:
    pyproject = Path("pyproject.toml")
    backup = tmp_path / "pyproject.toml.bak"
    backup.write_text(pyproject.read_text(encoding="utf-8"), encoding="utf-8")
    pyproject.rename(pyproject.with_suffix(".bak"))
    try:
        version = get_version()
        assert version == "0.0.0-dev" or re.fullmatch(r"\d+\.\d+\.\d+(\+g[0-9a-f]{7,})?", version)
    finally:
        pyproject.with_suffix(".bak").rename(pyproject)


def test_util_003_get_filename_creates_dir(tmp_path: Path) -> None:
    target_dir = tmp_path / ".cache" / "logs"
    path = get_filename("T_", ".log", str(target_dir))
    assert target_dir.exists()


def test_util_004_list_file_path_depth(tmp_path: Path) -> None:
    (tmp_path / "a" / "b").mkdir(parents=True, exist_ok=True)
    (tmp_path / "a" / "b" / "file.txt").write_text("x", encoding="utf-8")
    results = list(list_file_path(str(tmp_path), max_depth=1))
    assert all("file.txt" not in p for p in results)


def test_log_001_latest_log_symlink(workspace_a: Path) -> None:
    _ = run_cli(["--help"], cwd=workspace_a)
    latest = workspace_a / ".cache" / "latest.log"
    assert latest.exists()


def test_prof_001_cprofile_enabled(tmp_path: Path) -> None:
    @func_cprofile
    def _work():
        return sum(range(100))

    builtins.ENABLE_CPROFILE = True
    try:
        assert _work() == 4950
    finally:
        builtins.ENABLE_CPROFILE = False
