"""Validate release binaries as standalone single-file artifacts across platforms."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

SYSTEM_MACOS_PREFIXES = (
    "/System/Library/",
    "/usr/lib/",
    "/System/iOSSupport/usr/lib/",
)
SYSTEM_WINDOWS_DLLS = {
    "ADVAPI32.DLL",
    "BCRYPT.DLL",
    "CABINET.DLL",
    "COMBASE.DLL",
    "COMCTL32.DLL",
    "COMDLG32.DLL",
    "CRYPT32.DLL",
    "DBGHELP.DLL",
    "GDI32.DLL",
    "IMM32.DLL",
    "IPHLPAPI.DLL",
    "KERNEL32.DLL",
    "KERNELBASE.DLL",
    "NETAPI32.DLL",
    "NTDLL.DLL",
    "OLE32.DLL",
    "OLEAUT32.DLL",
    "PSAPI.DLL",
    "RPCRT4.DLL",
    "SECHOST.DLL",
    "SHELL32.DLL",
    "SHLWAPI.DLL",
    "USER32.DLL",
    "USERENV.DLL",
    "UCRTBASE.DLL",
    "VCRUNTIME140.DLL",
    "VCRUNTIME140_1.DLL",
    "VERSION.DLL",
    "WINMM.DLL",
    "WS2_32.DLL",
}
SYSTEM_WINDOWS_PREFIXES = ("API-MS-WIN-", "EXT-MS-WIN-")


def _run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, capture_output=True, text=True)


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    parts = [result.stdout.strip(), result.stderr.strip()]
    return "\n".join(part for part in parts if part).strip()


def _require_tool(name: str) -> None:
    if shutil.which(name):
        return
    raise RuntimeError(f"Required tool '{name}' is not available in PATH.")


def _detect_platform_name(explicit_platform: str | None = None) -> str:
    value = (explicit_platform or platform.system() or "").strip().lower()
    if value in {"linux"}:
        return "linux"
    if value in {"darwin", "macos", "mac"}:
        return "macos"
    if value in {"windows", "windows_nt"}:
        return "windows"
    if value.startswith(("mingw", "msys", "cygwin")):
        return "windows"
    raise RuntimeError(f"Unsupported platform for release-binary validation: {value or 'unknown'}")


def _has_dynamic_dependencies(readelf_output: str) -> bool:
    return "(NEEDED)" in readelf_output


def _ldd_indicates_standalone(ldd_output: str) -> bool:
    normalized = ldd_output.strip().lower()
    return "not a dynamic executable" in normalized or "statically linked" in normalized


def _parse_otool_dependencies(otool_output: str) -> list[str]:
    dependencies: list[str] = []
    for line in otool_output.splitlines()[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        dependency = stripped.split(" (compatibility version", 1)[0].strip()
        if dependency:
            dependencies.append(dependency)
    return dependencies


def _is_allowed_macos_dependency(dependency: str, binary_path: Path) -> bool:
    normalized = dependency.strip()
    if normalized == str(binary_path):
        return True
    return normalized.startswith(SYSTEM_MACOS_PREFIXES)


def _load_windows_imports(binary_path: Path) -> list[str]:
    try:
        import pefile  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised on Windows CI
        raise RuntimeError("Python package 'pefile' is required for Windows release-binary validation.") from exc

    pe = pefile.PE(str(binary_path), fast_load=True)
    try:
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]],
        )
        imports: list[str] = []
        for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
            dll_name = getattr(entry, "dll", b"") or b""
            imports.append(dll_name.decode("utf-8", errors="ignore"))
        return imports
    finally:
        pe.close()


def _is_allowed_windows_dependency(dll_name: str) -> bool:
    normalized = dll_name.strip().upper()
    if not normalized:
        return False
    if normalized in SYSTEM_WINDOWS_DLLS:
        return True
    return normalized.startswith(SYSTEM_WINDOWS_PREFIXES)


def _verify_linux_binary(binary_path: Path) -> None:
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


def _verify_macos_binary(binary_path: Path) -> None:
    _require_tool("otool")
    otool_result = _run_command(["otool", "-L", str(binary_path)])
    otool_output = _combined_output(otool_result)
    if otool_result.returncode != 0:
        raise RuntimeError(f"`otool -L` failed for {binary_path}:\n{otool_output}")

    dependencies = _parse_otool_dependencies(otool_output)
    unexpected = [dep for dep in dependencies if not _is_allowed_macos_dependency(dep, binary_path)]
    if unexpected:
        joined = "\n".join(unexpected)
        raise RuntimeError("macOS binary depends on non-system dynamic libraries/frameworks:\n" f"{joined}")


def _verify_windows_binary(binary_path: Path) -> None:
    imports = _load_windows_imports(binary_path)
    unexpected = [dll for dll in imports if not _is_allowed_windows_dependency(dll)]
    if unexpected:
        joined = "\n".join(sorted(unexpected))
        raise RuntimeError(
            "Windows binary imports non-system DLLs and is not a standalone single-file artifact:\n" f"{joined}"
        )


def verify_release_binary(binary_path: Path, *, platform_name: str | None = None) -> None:
    if not binary_path.is_file():
        raise RuntimeError(f"Binary not found: {binary_path}")

    detected_platform = _detect_platform_name(platform_name)
    if detected_platform == "linux":
        _verify_linux_binary(binary_path)
        return
    if detected_platform == "macos":
        _verify_macos_binary(binary_path)
        return
    if detected_platform == "windows":
        _verify_windows_binary(binary_path)
        return
    raise RuntimeError(f"Unsupported platform for release-binary validation: {detected_platform}")


def _parse_args(argv: list[str]) -> tuple[str | None, str]:
    args = list(argv[1:])
    platform_name = None
    if len(args) >= 2 and args[0] == "--platform":
        platform_name = args[1]
        args = args[2:]

    if len(args) != 1:
        raise RuntimeError(
            "Usage: python scripts/check_linux_standalone_binary.py [--platform linux|macos|windows] <binary>"
        )
    return platform_name, args[0]


def main(argv: list[str]) -> int:
    try:
        platform_name, binary_path = _parse_args(argv)
        verify_release_binary(Path(binary_path), platform_name=platform_name)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Verified standalone release binary: {binary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
