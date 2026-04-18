"""Tests for src.install_utils."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from src import install_utils


def test_resolve_managed_install_layout_for_bin_dir() -> None:
    layout = install_utils.resolve_managed_install_layout(
        "/tmp/example/bin",
        platform_name="linux",
    )
    assert layout.install_dir == "/tmp/example/bin"
    assert layout.launcher_path == "/tmp/example/bin/projman"
    assert layout.runtime_root == "/tmp/example/lib/projman"
    assert layout.venv_dir == "/tmp/example/lib/projman/venv"
    assert layout.runtime_executable == "/tmp/example/lib/projman/venv/bin/projman"


def test_install_wheel_into_managed_runtime_writes_launcher(tmp_path: Path) -> None:
    install_dir = tmp_path / "bin"
    wheel_path = tmp_path / "projman.whl"
    wheel_path.write_text("dummy", encoding="utf-8")

    calls: list[list[str]] = []

    def fake_run(args, check, capture_output, text):  # noqa: ANN001
        calls.append(list(args))
        if args[:3] == [os.sys.executable, "-m", "venv"]:
            venv_dir = Path(args[3])
            runtime_executable = venv_dir / "bin" / "projman"
            pip_path = venv_dir / "bin" / "pip"
            runtime_executable.parent.mkdir(parents=True, exist_ok=True)
            runtime_executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            pip_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            os.chmod(runtime_executable, 0o755)
            os.chmod(pip_path, 0o755)
        return None

    with patch.object(install_utils.subprocess, "run", side_effect=fake_run):
        version = install_utils.install_wheel_into_managed_runtime(
            str(wheel_path),
            str(install_dir),
            platform_name="linux",
            python_executable=os.sys.executable,
            verifier=lambda path: f"verified:{path}",
        )

    assert calls[0][:3] == [os.sys.executable, "-m", "venv"]
    assert calls[0][3] == str(tmp_path / "lib" / "projman" / "venv")
    assert calls[1][1:4] == ["install", "--upgrade", "--force-reinstall"]
    assert calls[1][-1] == str(wheel_path)
    launcher = install_dir / "projman"
    runtime_dir = tmp_path / "lib" / "projman" / "venv" / "bin" / "projman"
    assert launcher.exists()
    assert runtime_dir.exists()
    assert launcher.read_text(encoding="utf-8") == f'#!/bin/sh\nexec "{runtime_dir}" "$@"\n'
    assert version == f"verified:{launcher}"
