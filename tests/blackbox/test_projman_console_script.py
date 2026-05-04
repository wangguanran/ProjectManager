"""Blackbox tests for the installed `projman` console script."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import toml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _projman_env() -> dict:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    current_bin = Path(sys.executable).parent
    env["PATH"] = f"{current_bin}{os.pathsep}{env.get('PATH', '')}"
    return env


def _require_projman_command(env: dict) -> str:
    override = os.environ.get("PROJMAN_TEST_COMMAND")
    if override:
        return override

    resolved = shutil.which("projman", path=env.get("PATH", ""))
    assert resolved is not None, (
        "`projman` command not found. Install the package entry point before running this test, "
        "for example: python -m pip install -e ."
    )
    return resolved


def test_installed_projman_command_runs_cli_outputs(tmp_path: Path) -> None:
    """Install the package entry point and verify the real `projman` command."""

    env = _projman_env()
    projman = _require_projman_command(env)

    help_result = subprocess.run(
        [projman, "--help"],
        cwd=str(tmp_path),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert help_result.returncode == 0
    assert "supported operations" in (help_result.stdout + help_result.stderr)

    version_result = subprocess.run(
        [projman, "--version"],
        cwd=str(tmp_path),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert version_result.returncode == 0
    base_version = toml.load(str(REPO_ROOT / "pyproject.toml"))["project"]["version"]
    assert version_result.stdout.strip().startswith(base_version)

    update_result = subprocess.run(
        [projman, "update", "--dry-run", "--user"],
        cwd=str(tmp_path),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert update_result.returncode == 0
    assert "DRY-RUN: target install path:" in update_result.stdout
