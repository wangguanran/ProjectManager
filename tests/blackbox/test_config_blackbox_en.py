"""
Black-box configuration tests derived from docs/test_cases_en.md.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_cli(workdir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, "-m", "src", *args],
        cwd=str(workdir),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cfg_multiple_ini_files_is_deterministic_error(tmp_path: Path) -> None:
    """CFG-006: multiple ini files in board dir produces a deterministic non-zero error."""
    # Minimal common config (avoid unrelated warnings in this test).
    (tmp_path / "projects" / "common").mkdir(parents=True, exist_ok=True)
    (tmp_path / "projects" / "common" / "common.ini").write_text("[common]\n", encoding="utf-8")

    board_dir = tmp_path / "projects" / "boardA"
    board_dir.mkdir(parents=True, exist_ok=True)

    # Two ini files in the same board dir should fail.
    (board_dir / "boardA.ini").write_text("[projA]\nPROJECT_NAME=projA\n", encoding="utf-8")
    (board_dir / "extra.ini").write_text("[projA]\nPROJECT_NAME=projA\n", encoding="utf-8")

    cp = _run_cli(tmp_path, "po_list", "projA", "--short")
    assert cp.returncode != 0
    combined = (cp.stdout + cp.stderr).lower()
    assert "multiple ini files found" in combined
