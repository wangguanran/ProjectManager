"""Tests for the Linux standalone binary verification helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from subprocess import CompletedProcess

import pytest


def _load_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_linux_standalone_binary.py"
    spec = importlib.util.spec_from_file_location("check_linux_standalone_binary", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_ldd_standalone_detection_accepts_non_dynamic_text() -> None:
    mod = _load_module()
    assert mod._ldd_indicates_standalone("\tstatically linked\n")
    assert mod._ldd_indicates_standalone("\tnot a dynamic executable\n")


def test_has_dynamic_dependencies_flags_needed_entries() -> None:
    mod = _load_module()
    assert mod._has_dynamic_dependencies("0x0000000000000001 (NEEDED) Shared library: [libc.so.6]")


def test_verify_linux_standalone_binary_passes_without_needed_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mod = _load_module()
    binary = tmp_path / "projman"
    binary.write_bytes(b"binary")

    monkeypatch.setattr(mod.shutil, "which", lambda _: "/usr/bin/fake")

    def fake_run(args: list[str]) -> CompletedProcess[str]:
        if args[0] == "readelf":
            return CompletedProcess(args, 0, "There is no dynamic section in this file.\n", "")
        if args[0] == "ldd":
            return CompletedProcess(args, 1, "\tnot a dynamic executable\n", "")
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(mod, "_run_command", fake_run)
    mod.verify_linux_standalone_binary(binary)


def test_verify_linux_standalone_binary_rejects_needed_entries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mod = _load_module()
    binary = tmp_path / "projman"
    binary.write_bytes(b"binary")

    monkeypatch.setattr(mod.shutil, "which", lambda _: "/usr/bin/fake")

    def fake_run(args: list[str]) -> CompletedProcess[str]:
        if args[0] == "readelf":
            return CompletedProcess(
                args,
                0,
                "0x0000000000000001 (NEEDED) Shared library: [libpython3.12.so.1.0]\n",
                "",
            )
        if args[0] == "ldd":
            return CompletedProcess(args, 0, "\tlinux-vdso.so.1 (0x0000)\n", "")
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(mod, "_run_command", fake_run)

    with pytest.raises(RuntimeError, match="still declares shared-library dependencies"):
        mod.verify_linux_standalone_binary(binary)


def test_verify_linux_standalone_binary_rejects_dynamic_ldd_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mod = _load_module()
    binary = tmp_path / "projman"
    binary.write_bytes(b"binary")

    monkeypatch.setattr(mod.shutil, "which", lambda _: "/usr/bin/fake")

    def fake_run(args: list[str]) -> CompletedProcess[str]:
        if args[0] == "readelf":
            return CompletedProcess(args, 0, "There is no dynamic section in this file.\n", "")
        if args[0] == "ldd":
            return CompletedProcess(
                args,
                0,
                "\tlibc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x0000)\n",
                "",
            )
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(mod, "_run_command", fake_run)

    with pytest.raises(RuntimeError, match="not standalone according to `ldd`"):
        mod.verify_linux_standalone_binary(binary)
