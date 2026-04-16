"""Validate that a Linux binary has no external shared-library dependencies."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, capture_output=True, text=True)


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    parts = [result.stdout.strip(), result.stderr.strip()]
    return "\n".join(part for part in parts if part).strip()


def _has_dynamic_dependencies(readelf_output: str) -> bool:
    return "(NEEDED)" in readelf_output


def _ldd_indicates_standalone(ldd_output: str) -> bool:
    normalized = ldd_output.strip().lower()
    return "not a dynamic executable" in normalized or "statically linked" in normalized


def _require_tool(name: str) -> None:
    if shutil.which(name):
        return
    raise RuntimeError(f"Required tool '{name}' is not available in PATH.")


def verify_linux_standalone_binary(binary_path: Path) -> None:
    if not binary_path.is_file():
        raise RuntimeError(f"Binary not found: {binary_path}")

    _require_tool("readelf")
    _require_tool("ldd")

    readelf_result = _run_command(["readelf", "-d", str(binary_path)])
    readelf_output = _combined_output(readelf_result)
    if readelf_result.returncode != 0:
        raise RuntimeError(f"`readelf -d` failed for {binary_path}:\n{readelf_output}")
    if _has_dynamic_dependencies(readelf_output):
        raise RuntimeError("Linux binary still declares shared-library dependencies:\n" f"{readelf_output}")

    ldd_result = _run_command(["ldd", str(binary_path)])
    ldd_output = _combined_output(ldd_result)
    if not _ldd_indicates_standalone(ldd_output):
        raise RuntimeError("Linux binary is not standalone according to `ldd`:\n" f"{ldd_output}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python scripts/check_linux_standalone_binary.py <binary>", file=sys.stderr)
        return 2

    try:
        verify_linux_standalone_binary(Path(argv[1]))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Verified standalone Linux binary: {argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
