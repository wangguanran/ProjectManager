"""Blackbox test fixtures and helpers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(
    cmd: List[str], cwd: Path, env: Dict[str, str] | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    merged_env = os.environ.copy()
    merged_env["PYTHONPATH"] = str(REPO_ROOT)
    if env:
        merged_env.update(env)
    return subprocess.run(cmd, cwd=str(cwd), env=merged_env, text=True, capture_output=True, check=check)


def run_cli(
    args: List[str], cwd: Path, env: Dict[str, str] | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    return _run([os.environ.get("PYTHON", os.sys.executable), "-m", "src", *args], cwd=cwd, env=env, check=check)


def init_git_repo(root: Path) -> None:
    _run(["git", "init"], cwd=root)
    _run(["git", "config", "user.email", "test@example.com"], cwd=root)
    _run(["git", "config", "user.name", "Test User"], cwd=root)
    (root / "baseline.txt").write_text("baseline", encoding="utf-8")
    _run(["git", "add", "baseline.txt"], cwd=root)
    _run(["git", "commit", "-m", "init"], cwd=root)


def setup_dataset_a(root: Path) -> None:
    init_git_repo(root)
    projects = root / "projects"
    common_dir = projects / "common"
    common_dir.mkdir(parents=True, exist_ok=True)
    common_ini = common_dir / "common.ini"
    common_ini.write_text(
        "[common]\n"
        "PROJECT_PLATFORM = platA\n"
        "PROJECT_CUSTOMER = custA\n"
        "PROJECT_PO_CONFIG = po_base\n"
        "\n"
        "[po-po_base]\n"
        "PROJECT_PO_DIR = custom\n"
        "PROJECT_PO_FILE_COPY = cfg/*.ini:out/cfg/ \\\n"
        " data/*:out/data/\n",
        encoding="utf-8",
    )

    board_dir = projects / "boardA"
    board_dir.mkdir(parents=True, exist_ok=True)
    board_ini = board_dir / "boardA.ini"
    board_ini.write_text(
        "[boardA]\n"
        "PROJECT_NAME = boardA\n"
        "PROJECT_PO_CONFIG = po_base\n"
        "\n"
        "[projA]\n"
        "PROJECT_NAME = projA\n"
        "PROJECT_PLATFORM = platA\n"
        "PROJECT_CUSTOMER = custA\n"
        "PROJECT_PO_CONFIG = po_base po_extra\n"
        "\n"
        "[projA-sub]\n"
        "PROJECT_NAME = projA_sub\n"
        "PROJECT_PO_CONFIG = po_sub\n",
        encoding="utf-8",
    )

    po_base = board_dir / "po" / "po_base"
    (po_base / "patches").mkdir(parents=True, exist_ok=True)
    (po_base / "overrides").mkdir(parents=True, exist_ok=True)
    (po_base / "custom" / "cfg").mkdir(parents=True, exist_ok=True)
    (po_base / "custom" / "data").mkdir(parents=True, exist_ok=True)
    (po_base / "custom" / "cfg" / "sample.ini").write_text("k=v", encoding="utf-8")
    (po_base / "custom" / "data" / "sample.dat").write_text("data", encoding="utf-8")

    src_dir = root / "src"
    src_dir.mkdir(exist_ok=True)
    tmp_file = src_dir / "tmp_file.txt"
    tmp_file.write_text("line1", encoding="utf-8")
    _run(["git", "add", "src/tmp_file.txt"], cwd=root)
    _run(["git", "commit", "-m", "add tmp file"], cwd=root)
    tmp_file.write_text("line1\nline2", encoding="utf-8")
    patch_path = po_base / "patches" / "tmp_file.patch"
    diff = _run(["git", "diff", "--", "src/tmp_file.txt"], cwd=root, check=True)
    patch_path.write_text(diff.stdout, encoding="utf-8")
    shutil.copy2(tmp_file, po_base / "overrides" / "tmp_file.txt")


def setup_dataset_b(root: Path) -> None:
    setup_dataset_a(root)
    repo1 = root / "repo1"
    repo2 = root / "repo2"
    repo1.mkdir(parents=True, exist_ok=True)
    repo2.mkdir(parents=True, exist_ok=True)
    _run(["git", "init"], cwd=repo1)
    _run(["git", "config", "user.email", "test@example.com"], cwd=repo1)
    _run(["git", "config", "user.name", "Test User"], cwd=repo1)
    (repo1 / "a.txt").write_text("r1", encoding="utf-8")
    _run(["git", "add", "a.txt"], cwd=repo1)
    _run(["git", "commit", "-m", "r1"], cwd=repo1)
    _run(["git", "init"], cwd=repo2)
    _run(["git", "config", "user.email", "test@example.com"], cwd=repo2)
    _run(["git", "config", "user.name", "Test User"], cwd=repo2)
    (repo2 / "b.txt").write_text("r2", encoding="utf-8")
    _run(["git", "add", "b.txt"], cwd=repo2)
    _run(["git", "commit", "-m", "r2"], cwd=repo2)

    repo_dir = root / ".repo"
    (repo_dir / "manifests").mkdir(parents=True, exist_ok=True)
    (repo_dir / "manifest.xml").write_text(
        "<manifest>\n"
        '  <project name="repo1" path="repo1" />\n'
        '  <project name="repo2" path="repo2" />\n'
        "</manifest>\n",
        encoding="utf-8",
    )


@pytest.fixture()
def workspace_a(tmp_path: Path) -> Path:
    setup_dataset_a(tmp_path)
    return tmp_path


@pytest.fixture()
def workspace_b(tmp_path: Path) -> Path:
    setup_dataset_b(tmp_path)
    return tmp_path


@pytest.fixture()
def empty_workspace(tmp_path: Path) -> Path:
    return tmp_path
