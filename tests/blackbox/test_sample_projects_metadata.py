"""Regression tests for committed sample project metadata."""

from __future__ import annotations

import json
import re
from pathlib import Path

SENSITIVE_PATH_PATTERNS = [
    re.compile(r"/Users/[^/\s\"]+"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"\.codex"),
]


def test_sensitive_path_patterns_ignore_documented_home_placeholders() -> None:
    placeholder_path = "/home/<user>/ProjectManager"
    real_user_path = "/home/alice/ProjectManager"
    linux_home_pattern = SENSITIVE_PATH_PATTERNS[1]

    assert linux_home_pattern.search(placeholder_path) is None
    assert linux_home_pattern.search(real_user_path) is not None


def test_sample_projects_metadata_uses_portable_relative_paths() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sample_files = sorted((repo_root / "projects").glob("*/projects.json"))

    assert sample_files
    for sample_file in sample_files:
        text = sample_file.read_text(encoding="utf-8")
        for pattern in SENSITIVE_PATH_PATTERNS:
            assert pattern.search(text) is None

        data = json.loads(text)
        board_path = data.get("board_path", "")
        assert Path(board_path).is_absolute() is False

        for project in data.get("projects", []):
            ini_file = project.get("ini_file")
            if ini_file:
                assert Path(ini_file).is_absolute() is False
