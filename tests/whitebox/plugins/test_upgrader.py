"""Tests for src.plugins.upgrader."""

import hashlib
import os
import sys
from unittest.mock import patch


class TestUpgrader:
    """Test cases for upgrade operation and helpers."""

    def setup_method(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        import src.plugins.upgrader as upgrader

        self.upgrader = upgrader

    def test_select_release_asset_prefers_exact_platform_and_arch(self):
        release_data = {
            "assets": [
                {"name": "projman-linux-arm64", "browser_download_url": "https://example.com/arm64"},
                {"name": "projman-linux-x86_64", "browser_download_url": "https://example.com/x86_64"},
            ]
        }
        asset = self.upgrader._select_release_asset(release_data, "linux", "x86_64")
        assert asset is not None
        assert asset["name"] == "projman-linux-x86_64"

    def test_select_release_asset_skips_checksum_files(self):
        release_data = {
            "assets": [
                {
                    "name": "projman-linux-x86_64.sha256",
                    "browser_download_url": "https://example.com/projman-linux-x86_64.sha256",
                },
                {
                    "name": "projman-linux-x86_64",
                    "browser_download_url": "https://example.com/projman-linux-x86_64",
                },
            ]
        }
        asset = self.upgrader._select_release_asset(release_data, "linux", "x86_64")
        assert asset is not None
        assert asset["name"] == "projman-linux-x86_64"

    def test_upgrade_dry_run_succeeds_without_network(self, tmp_path):
        result = self.upgrader.upgrade(
            env={},
            projects_info={},
            prefix=str(tmp_path / "bin"),
            dry_run=True,
        )
        assert result is True

    def test_upgrade_installs_selected_asset(self, tmp_path):
        install_dir = tmp_path / "install-bin"
        downloaded = tmp_path / "downloaded-projman"
        downloaded.write_bytes(b"projman-binary")
        release_data = {
            "tag_name": "v0.0.12",
            "assets": [
                {
                    "name": "projman-linux-x86_64",
                    "browser_download_url": "https://example.com/projman-linux-x86_64",
                }
            ],
        }

        with (
            patch.object(self.upgrader, "_normalize_platform_name", return_value="linux"),
            patch.object(self.upgrader, "_normalize_arch", return_value="x86_64"),
            patch.object(self.upgrader, "_is_admin_user", return_value=False),
            patch.object(self.upgrader, "_http_get_json", return_value=release_data),
            patch.object(self.upgrader, "_download_file", return_value=str(downloaded)),
            patch.object(self.upgrader, "_verify_binary", return_value="0.0.12"),
            patch.object(self.upgrader, "_path_contains", return_value=True),
        ):
            result = self.upgrader.upgrade(
                env={},
                projects_info={},
                prefix=str(install_dir),
            )

        assert result is True
        target = install_dir / "projman"
        assert target.exists()
        assert target.read_bytes() == b"projman-binary"

    def test_upgrade_verifies_sha256_when_available(self, tmp_path):
        install_dir = tmp_path / "install-bin"
        downloaded = tmp_path / "downloaded-projman"
        payload = b"projman-binary"
        downloaded.write_bytes(payload)

        checksum = hashlib.sha256(payload).hexdigest()
        checksum_file = tmp_path / "downloaded-projman.sha256"
        checksum_file.write_text(f"{checksum}  projman-linux-x86_64\n", encoding="utf-8")

        release_data = {
            "tag_name": "v0.0.12",
            "assets": [
                {
                    "name": "projman-linux-x86_64",
                    "browser_download_url": "https://example.com/projman-linux-x86_64",
                },
                {
                    "name": "projman-linux-x86_64.sha256",
                    "browser_download_url": "https://example.com/projman-linux-x86_64.sha256",
                },
            ],
        }

        def download_side_effect(url: str, _token: str) -> str:
            if url.endswith(".sha256"):
                return str(checksum_file)
            return str(downloaded)

        with (
            patch.object(self.upgrader, "_normalize_platform_name", return_value="linux"),
            patch.object(self.upgrader, "_normalize_arch", return_value="x86_64"),
            patch.object(self.upgrader, "_is_admin_user", return_value=False),
            patch.object(self.upgrader, "_http_get_json", return_value=release_data),
            patch.object(self.upgrader, "_download_file", side_effect=download_side_effect),
            patch.object(self.upgrader, "_verify_binary", return_value="0.0.12"),
            patch.object(self.upgrader, "_path_contains", return_value=True),
        ):
            result = self.upgrader.upgrade(
                env={},
                projects_info={},
                prefix=str(install_dir),
            )

        assert result is True
        target = install_dir / "projman"
        assert target.exists()
        assert target.read_bytes() == payload

    def test_upgrade_fails_on_sha256_mismatch(self, tmp_path):
        install_dir = tmp_path / "install-bin"
        downloaded = tmp_path / "downloaded-projman"
        payload = b"projman-binary"
        downloaded.write_bytes(payload)

        checksum_file = tmp_path / "downloaded-projman.sha256"
        checksum_file.write_text(f"{'0' * 64}  projman-linux-x86_64\n", encoding="utf-8")

        release_data = {
            "tag_name": "v0.0.12",
            "assets": [
                {
                    "name": "projman-linux-x86_64",
                    "browser_download_url": "https://example.com/projman-linux-x86_64",
                },
                {
                    "name": "projman-linux-x86_64.sha256",
                    "browser_download_url": "https://example.com/projman-linux-x86_64.sha256",
                },
            ],
        }

        def download_side_effect(url: str, _token: str) -> str:
            if url.endswith(".sha256"):
                return str(checksum_file)
            return str(downloaded)

        with (
            patch.object(self.upgrader, "_normalize_platform_name", return_value="linux"),
            patch.object(self.upgrader, "_normalize_arch", return_value="x86_64"),
            patch.object(self.upgrader, "_is_admin_user", return_value=False),
            patch.object(self.upgrader, "_http_get_json", return_value=release_data),
            patch.object(self.upgrader, "_download_file", side_effect=download_side_effect),
        ):
            result = self.upgrader.upgrade(
                env={},
                projects_info={},
                prefix=str(install_dir),
            )

        assert result is False
        assert not (install_dir / "projman").exists()

    def test_upgrade_requires_checksum_when_flag_set(self, tmp_path):
        install_dir = tmp_path / "install-bin"
        downloaded = tmp_path / "downloaded-projman"
        downloaded.write_bytes(b"projman-binary")

        release_data = {
            "tag_name": "v0.0.12",
            "assets": [
                {
                    "name": "projman-linux-x86_64",
                    "browser_download_url": "https://example.com/projman-linux-x86_64",
                }
            ],
        }

        with (
            patch.object(self.upgrader, "_normalize_platform_name", return_value="linux"),
            patch.object(self.upgrader, "_normalize_arch", return_value="x86_64"),
            patch.object(self.upgrader, "_is_admin_user", return_value=False),
            patch.object(self.upgrader, "_http_get_json", return_value=release_data),
            patch.object(self.upgrader, "_download_file", return_value=str(downloaded)),
        ):
            result = self.upgrader.upgrade(
                env={},
                projects_info={},
                prefix=str(install_dir),
                require_checksum=True,
            )

        assert result is False

    def test_upgrade_fails_when_matching_asset_missing(self):
        release_data = {
            "tag_name": "v0.0.12",
            "assets": [
                {
                    "name": "projman-linux-arm64",
                    "browser_download_url": "https://example.com/projman-linux-arm64",
                }
            ],
        }
        with (
            patch.object(self.upgrader, "_normalize_platform_name", return_value="linux"),
            patch.object(self.upgrader, "_normalize_arch", return_value="x86_64"),
            patch.object(self.upgrader, "_is_admin_user", return_value=False),
            patch.object(self.upgrader, "_http_get_json", return_value=release_data),
        ):
            result = self.upgrader.upgrade(
                env={},
                projects_info={},
                prefix="/tmp/unused",
            )
        assert result is False
