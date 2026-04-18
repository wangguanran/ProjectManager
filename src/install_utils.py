"""Helpers for managed non-onefile installs."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass(frozen=True)
class ManagedInstallLayout:
    """Filesystem layout for a managed package install."""

    install_dir: str
    launcher_path: str
    runtime_root: str
    venv_dir: str
    runtime_executable: str


def _launcher_extension(platform_name: str) -> str:
    return ".cmd" if platform_name == "windows" else ""


def resolve_managed_install_layout(
    install_dir: str,
    *,
    platform_name: str,
    launcher_name: str = "projman",
) -> ManagedInstallLayout:
    """Resolve launcher/runtime paths for a managed package install."""

    expanded_dir = os.path.abspath(os.path.expanduser(install_dir))

    if platform_name == "windows":
        runtime_root = os.path.join(expanded_dir, "runtime")
        venv_dir = os.path.join(runtime_root, "venv")
        runtime_executable = os.path.join(venv_dir, "Scripts", f"{launcher_name}.exe")
        launcher_path = os.path.join(expanded_dir, f"{launcher_name}.cmd")
        return ManagedInstallLayout(
            install_dir=expanded_dir,
            launcher_path=launcher_path,
            runtime_root=runtime_root,
            venv_dir=venv_dir,
            runtime_executable=runtime_executable,
        )

    install_path = Path(expanded_dir)
    if install_path.name == "bin":
        runtime_root = str(install_path.parent / "lib" / launcher_name)
    else:
        runtime_root = str(install_path / f".{launcher_name}-runtime")

    venv_dir = os.path.join(runtime_root, "venv")
    runtime_executable = os.path.join(venv_dir, "bin", launcher_name)
    launcher_path = os.path.join(expanded_dir, launcher_name)
    return ManagedInstallLayout(
        install_dir=expanded_dir,
        launcher_path=launcher_path,
        runtime_root=runtime_root,
        venv_dir=venv_dir,
        runtime_executable=runtime_executable,
    )


def _default_verify_executable(executable_path: str) -> str:
    completed = subprocess.run(  # noqa: S603
        [executable_path, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip() or "unknown error"
        raise RuntimeError(f"Installed executable verification failed: {detail}")
    return (completed.stdout or completed.stderr or "").strip()


def _write_launcher(layout: ManagedInstallLayout, *, platform_name: str) -> None:
    os.makedirs(layout.install_dir, exist_ok=True)
    if platform_name == "windows":
        content = "@echo off\r\n" f'"{layout.runtime_executable}" %*\r\n'
        Path(layout.launcher_path).write_text(content, encoding="utf-8")
        return

    content = "#!/bin/sh\n" f'exec "{layout.runtime_executable}" "$@"\n'
    Path(layout.launcher_path).write_text(content, encoding="utf-8")
    os.chmod(layout.launcher_path, 0o755)


def install_wheel_into_managed_runtime(
    wheel_path: str,
    install_dir: str,
    *,
    platform_name: str,
    python_executable: Optional[str] = None,
    launcher_name: str = "projman",
    verifier: Optional[Callable[[str], str]] = None,
) -> str:
    """Install a wheel into a managed runtime and expose a launcher."""

    layout = resolve_managed_install_layout(
        install_dir,
        platform_name=platform_name,
        launcher_name=launcher_name,
    )
    verify_executable = verifier or _default_verify_executable

    runtime_parent = os.path.dirname(layout.runtime_root)
    os.makedirs(runtime_parent, exist_ok=True)
    backup_runtime = ""
    backup_launcher = ""
    final_version = ""

    try:
        if os.path.exists(layout.runtime_root):
            backup_runtime = tempfile.mkdtemp(
                prefix=f"{launcher_name}-runtime-backup-",
                dir=runtime_parent,
            )
            shutil.rmtree(backup_runtime)
            os.replace(layout.runtime_root, backup_runtime)

        launcher_parent = os.path.dirname(layout.launcher_path)
        os.makedirs(launcher_parent, exist_ok=True)
        if os.path.exists(layout.launcher_path):
            fd, backup_launcher = tempfile.mkstemp(
                prefix=f"{launcher_name}-launcher-backup-",
                suffix=_launcher_extension(platform_name),
                dir=launcher_parent,
            )
            os.close(fd)
            os.remove(backup_launcher)
            os.replace(layout.launcher_path, backup_launcher)

        subprocess.run(  # noqa: S603
            [python_executable or sys.executable, "-m", "venv", layout.venv_dir],
            check=True,
            capture_output=True,
            text=True,
        )
        pip_path = (
            os.path.join(layout.venv_dir, "Scripts", "pip.exe")
            if platform_name == "windows"
            else os.path.join(layout.venv_dir, "bin", "pip")
        )
        subprocess.run(  # noqa: S603
            [pip_path, "install", "--upgrade", "--force-reinstall", wheel_path],
            check=True,
            capture_output=True,
            text=True,
        )
        verify_executable(layout.runtime_executable)
        _write_launcher(layout, platform_name=platform_name)
        final_version = verify_executable(layout.launcher_path)
    except Exception:
        if os.path.exists(layout.runtime_root):
            shutil.rmtree(layout.runtime_root, ignore_errors=True)
        if backup_runtime and os.path.exists(backup_runtime):
            os.replace(backup_runtime, layout.runtime_root)
        if backup_launcher and os.path.exists(backup_launcher):
            if os.path.exists(layout.launcher_path):
                os.remove(layout.launcher_path)
            os.replace(backup_launcher, layout.launcher_path)
        raise

    if backup_runtime and os.path.exists(backup_runtime):
        shutil.rmtree(backup_runtime, ignore_errors=True)
    if backup_launcher and os.path.exists(backup_launcher):
        os.remove(backup_launcher)

    return final_version
