"""
Upgrade command for projman.

Downloads the latest release binary from GitHub and installs it into the
selected install prefix.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import tempfile
import urllib.error
import urllib.request
from typing import Any, Dict, Mapping, Optional

from src.log_manager import log
from src.operations.registry import register


def _normalize_platform_name(system_name: Optional[str] = None) -> str:
    name = (system_name or platform.system() or "").strip().lower()
    if name in {"windows", "windows_nt"} or name.startswith(("mingw", "msys", "cygwin")):
        return "windows"
    if name == "darwin":
        return "macos"
    if name == "linux":
        return "linux"
    return "unknown"


def _normalize_arch(machine_name: Optional[str] = None) -> str:
    arch = (machine_name or platform.machine() or "").strip().lower()
    mapping = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }
    return mapping.get(arch, arch or "unknown")


def _is_admin_user() -> bool:
    if os.name == "nt":
        try:
            import ctypes

            windll = getattr(ctypes, "windll", None)
            if windll is None:
                return False
            return bool(windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            return False

    geteuid = getattr(os, "geteuid", None)
    if callable(geteuid):
        return bool(geteuid() == 0)
    return False


def _resolve_install_mode(system: Any, user: Any) -> str:
    if bool(system) and bool(user):
        raise ValueError("`--system` and `--user` cannot be used together.")
    if bool(system):
        return "system"
    if bool(user):
        return "user"
    return "auto"


def _resolve_install_dir(
    platform_name: str,
    install_mode: str,
    prefix: str,
    is_admin: bool,
    env_vars: Mapping[str, str],
) -> str:
    if prefix:
        return os.path.abspath(os.path.expanduser(prefix))

    home = os.path.expanduser("~")

    if platform_name == "windows":
        local_appdata = env_vars.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        program_files = env_vars.get("ProgramFiles") or r"C:\Program Files"
        if install_mode == "system":
            return os.path.join(program_files, "projman")
        if install_mode == "user":
            return os.path.join(local_appdata, "Programs", "projman")
        return (
            os.path.join(program_files, "projman")
            if is_admin
            else os.path.join(
                local_appdata,
                "Programs",
                "projman",
            )
        )

    if install_mode == "system":
        return "/usr/local/bin"
    if install_mode == "user":
        return os.path.join(home, ".local", "bin")
    return "/usr/local/bin" if is_admin else os.path.join(home, ".local", "bin")


def _release_api_url(owner: str, repo: str) -> str:
    return f"https://api.github.com/repos/{owner}/{repo}/releases/latest"


def _http_get_json(url: str, token: str) -> Dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} while requesting {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error while requesting {url}: {exc.reason}") from exc


def _download_file(url: str, token: str) -> str:
    headers = {"Accept": "application/octet-stream"}
    if token:
        headers["Authorization"] = f"token {token}"

    request = urllib.request.Request(url, headers=headers)
    fd, temp_path = tempfile.mkstemp(prefix="projman_upgrade_", suffix=".bin")
    os.close(fd)
    try:
        with urllib.request.urlopen(request, timeout=120) as response, open(temp_path, "wb") as temp_file:
            shutil.copyfileobj(response, temp_file)
        return temp_path
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def _select_checksum_asset(release_data: Dict[str, Any], asset_name: str) -> Optional[Dict[str, Any]]:
    assets = [asset for asset in (release_data.get("assets") or []) if isinstance(asset, dict)]
    candidates = [
        f"{asset_name}.sha256",
        f"{asset_name}.sha256.txt",
    ]
    for candidate in candidates:
        for asset in assets:
            name = str(asset.get("name") or "")
            if name == candidate and asset.get("browser_download_url"):
                return asset
    return None


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _parse_sha256sum_file(path: str) -> str:
    try:
        text = ""
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            text = handle.read()
    except OSError as exc:
        raise RuntimeError(f"Failed to read checksum file: {exc}") from exc

    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        token = line.split()[0].strip()
        if len(token) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in token):
            return token.lower()
        raise RuntimeError("Invalid sha256 checksum format.")

    raise RuntimeError("Empty sha256 checksum file.")


def _select_release_asset(release_data: Dict[str, Any], platform_name: str, arch: str) -> Optional[Dict[str, Any]]:
    assets = [asset for asset in (release_data.get("assets") or []) if isinstance(asset, dict)]
    ext = ".exe" if platform_name == "windows" else ""
    exact_candidates = [f"projman-{platform_name}-{arch}{ext}"]
    if platform_name == "linux" and arch == "x86_64":
        exact_candidates.append("multi-project-manager-linux-x64")

    def _is_checksum_asset(name: str) -> bool:
        lowered = name.lower()
        return lowered.endswith(".sha256") or lowered.endswith(".sha256.txt")

    for candidate in exact_candidates:
        for asset in assets:
            name = str(asset.get("name") or "")
            if name == candidate and asset.get("browser_download_url"):
                return asset

    for asset in assets:
        name = str(asset.get("name") or "")
        if _is_checksum_asset(name):
            continue
        if name.startswith(f"projman-{platform_name}-{arch}") and asset.get("browser_download_url"):
            return asset

    for asset in assets:
        name = str(asset.get("name") or "")
        if _is_checksum_asset(name):
            continue
        if name.startswith(f"projman-{platform_name}-") and asset.get("browser_download_url"):
            return asset

    if platform_name == "windows":
        for asset in assets:
            name = str(asset.get("name") or "")
            if _is_checksum_asset(name):
                continue
            if name.endswith(".exe") and asset.get("browser_download_url"):
                return asset

    return None


def _ensure_executable(file_path: str, platform_name: str) -> None:
    if platform_name == "windows":
        return
    mode = os.stat(file_path).st_mode
    os.chmod(file_path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _verify_binary(binary_path: str) -> str:
    try:
        completed = subprocess.run(
            [binary_path, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"Failed to execute '{binary_path} --version': {exc}") from exc

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        detail = stderr or stdout or "unknown error"
        raise RuntimeError(f"Installed binary verification failed: {detail}")

    version_output = (completed.stdout or completed.stderr or "").strip()
    if not version_output:
        raise RuntimeError("Installed binary verification failed: empty version output.")
    return version_output


def _path_contains(path_value: str) -> bool:
    normalized = os.path.normcase(os.path.normpath(os.path.abspath(path_value)))
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        candidate = os.path.normcase(os.path.normpath(os.path.abspath(entry)))
        if candidate == normalized:
            return True
    return False


@register(
    "upgrade",
    needs_repositories=False,
    needs_projects=False,
    desc="Upgrade projman by downloading the latest release binary",
)
def upgrade(
    env: Dict[str, Any],
    projects_info: Dict[str, Any],
    project_name: str = "",
    owner: str = "wangguanran",
    repo: str = "ProjectManager",
    token: str = "",
    system: bool = False,
    user: bool = False,
    prefix: str = "",
    dry_run: bool = False,
    require_checksum: bool = False,
) -> bool:
    """Upgrade projman from latest GitHub release binary.

    Args:
        owner (str): GitHub repository owner.
        repo (str): GitHub repository name.
        token (str): Optional GitHub token for rate-limit/private access.
        system (bool): Install to system location.
        user (bool): Install to user location.
        prefix (str): Install directory override.
        dry_run (bool): Print planned actions without writing files.
        require_checksum (bool): If True, require a matching sha256 asset and abort if missing.
    """

    _ = env
    _ = projects_info
    _ = project_name

    try:
        install_mode = _resolve_install_mode(system, user)
    except ValueError as exc:
        log.error("upgrade parameter error: %s", exc)
        print(f"Error: {exc}")
        return False

    platform_name = _normalize_platform_name()
    arch = _normalize_arch()
    is_admin = _is_admin_user()
    install_dir = _resolve_install_dir(
        platform_name=platform_name,
        install_mode=install_mode,
        prefix=str(prefix or "").strip(),
        is_admin=is_admin,
        env_vars=os.environ,
    )
    binary_name = "projman.exe" if platform_name == "windows" else "projman"
    target_path = os.path.join(install_dir, binary_name)

    if platform_name == "unknown":
        log.error("Unsupported platform for upgrade.")
        print("Error: unsupported platform; cannot determine release asset.")
        return False

    auth_token = str(token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    api_url = _release_api_url(owner, repo)

    if dry_run:
        print(f"DRY-RUN: platform={platform_name}, arch={arch}")
        print(f"DRY-RUN: target install path: {target_path}")
        print(f"DRY-RUN: latest release API: {api_url}")
        return True

    try:
        release_data = _http_get_json(api_url, auth_token)
    except RuntimeError as exc:
        log.error("Failed to fetch latest release metadata: %s", exc)
        print(f"Error: {exc}")
        return False

    asset = _select_release_asset(release_data, platform_name, arch)
    if not asset:
        asset_names = [str(item.get("name") or "") for item in (release_data.get("assets") or [])]
        log.error(
            "No matching release asset found for platform=%s arch=%s in assets=%s",
            platform_name,
            arch,
            asset_names,
        )
        print(
            f"Error: no matching release asset for platform={platform_name}, arch={arch}. "
            f"Available assets: {asset_names}"
        )
        return False

    download_url = str(asset.get("browser_download_url") or "").strip()
    if not download_url:
        print("Error: release asset missing browser_download_url.")
        return False

    release_tag = str(release_data.get("tag_name") or release_data.get("name") or "").strip()
    asset_name = str(asset.get("name") or "").strip()
    print(f"Latest release: {release_tag}")
    print(f"Selected asset: {asset_name}")
    print(f"Install path: {target_path}")

    temp_path = ""
    checksum_path = ""
    try:
        os.makedirs(install_dir, exist_ok=True)
        temp_path = _download_file(download_url, auth_token)

        checksum_asset = _select_checksum_asset(release_data, asset_name)
        if checksum_asset:
            checksum_url = str(checksum_asset.get("browser_download_url") or "").strip()
            if checksum_url:
                checksum_path = _download_file(checksum_url, auth_token)
                expected = _parse_sha256sum_file(checksum_path)
                actual = _sha256_file(temp_path)
                if actual.lower() != expected.lower():
                    raise RuntimeError(
                        f"sha256 mismatch for '{asset_name}': expected {expected}, got {actual}. "
                        "Refusing to install."
                    )
        else:
            if bool(require_checksum):
                raise RuntimeError(f"sha256 checksum asset not found for '{asset_name}'. Refusing to install.")
            log.warning(
                "sha256 checksum asset not found for '%s'; proceeding without integrity verification.", asset_name
            )

        os.replace(temp_path, target_path)
        temp_path = ""
        _ensure_executable(target_path, platform_name)
        version_output = _verify_binary(target_path)
    except PermissionError as exc:
        log.error("Permission denied while installing binary: %s", exc)
        print(
            f"Error: permission denied while installing to '{install_dir}'. "
            "Use '--user' or run with appropriate permissions."
        )
        return False
    except (OSError, RuntimeError) as exc:
        log.error("Upgrade install failed: %s", exc)
        print(f"Error: {exc}")
        return False
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        if checksum_path and os.path.exists(checksum_path):
            try:
                os.remove(checksum_path)
            except OSError:
                pass

    print(f"Upgrade completed: {target_path}")
    print(f"Verified version: {version_output}")
    if not _path_contains(install_dir):
        print(f"Warning: PATH does not include '{install_dir}'.")
    return True
