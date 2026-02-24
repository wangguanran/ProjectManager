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

    def test_update_dry_run_succeeds_without_network(self, tmp_path):
        result = self.upgrader.update(
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

    def test_upgrade_keeps_existing_binary_when_new_binary_fails_verification(self, tmp_path):
        install_dir = tmp_path / "install-bin"
        install_dir.mkdir(parents=True, exist_ok=True)
        target = install_dir / "projman"
        target.write_bytes(b"existing-projman-binary")

        downloaded = tmp_path / "downloaded-projman"
        downloaded.write_bytes(b"new-projman-binary")
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
            patch.object(
                self.upgrader,
                "_verify_binary",
                side_effect=RuntimeError("Installed binary verification failed: GLIBC_2.38 not found"),
            ),
        ):
            result = self.upgrader.upgrade(
                env={},
                projects_info={},
                prefix=str(install_dir),
            )

        assert result is False
        assert target.exists()
        assert target.read_bytes() == b"existing-projman-binary"

    def test_upgrade_beta_selects_prerelease(self, tmp_path):
        install_dir = tmp_path / "install-bin"
        downloaded = tmp_path / "downloaded-projman"
        downloaded.write_bytes(b"projman-binary")

        releases = [
            {
                "tag_name": "v0.0.12",
                "prerelease": False,
                "assets": [
                    {
                        "name": "projman-linux-x86_64",
                        "browser_download_url": "https://example.com/stable",
                    }
                ],
            },
            {
                "tag_name": "beta-0.0.13",
                "prerelease": True,
                "assets": [
                    {
                        "name": "projman-linux-x86_64",
                        "browser_download_url": "https://example.com/beta",
                    }
                ],
            },
        ]

        with (
            patch.object(self.upgrader, "_normalize_platform_name", return_value="linux"),
            patch.object(self.upgrader, "_normalize_arch", return_value="x86_64"),
            patch.object(self.upgrader, "_is_admin_user", return_value=False),
            patch.object(self.upgrader, "_http_get_json", return_value=releases),
            patch.object(self.upgrader, "_download_file", return_value=str(downloaded)),
            patch.object(self.upgrader, "_verify_binary", return_value="0.0.13"),
            patch.object(self.upgrader, "_path_contains", return_value=True),
        ):
            result = self.upgrader.upgrade(
                env={},
                projects_info={},
                prefix=str(install_dir),
                beta=True,
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

    def test_verify_binary_sanitizes_pyinstaller_env(self):
        captured: dict = {}

        class DummyCompleted:  # minimal subprocess.CompletedProcess-like object
            returncode = 0
            stdout = "0.0.1\n"
            stderr = ""

        def fake_run(*_args, **kwargs):
            captured["env"] = kwargs.get("env")
            return DummyCompleted()

        with (
            patch.dict(
                os.environ,
                {
                    "PYTHONHOME": "/tmp/_MEIparent",
                    "PYTHONPATH": "/tmp/_MEIparent",
                    "_MEIPASS2": "/tmp/_MEIparent",
                    "_PYI_APPLICATION_HOME_DIR": "/tmp/_MEIparent",
                    "DYLD_LIBRARY_PATH": "/tmp/bad",
                },
                clear=False,
            ),
            patch.object(self.upgrader.subprocess, "run", side_effect=fake_run),
        ):
            version = self.upgrader._verify_binary("/tmp/projman")

        assert version == "0.0.1"
        env = captured.get("env")
        assert isinstance(env, dict)
        assert env.get("PYINSTALLER_RESET_ENVIRONMENT") == "1"
        assert "PYTHONHOME" not in env
        assert "PYTHONPATH" not in env
        assert "_MEIPASS2" not in env
        assert "_PYI_APPLICATION_HOME_DIR" not in env
        assert "DYLD_LIBRARY_PATH" not in env

    def test_create_ssl_context_prefers_ssl_cert_file(self, tmp_path, monkeypatch):
        cafile = tmp_path / "custom_ca.pem"
        cafile.write_text("dummy", encoding="utf-8")
        monkeypatch.setenv("SSL_CERT_FILE", str(cafile))
        monkeypatch.delenv("SSL_CERT_DIR", raising=False)

        sentinel = object()
        with patch.object(self.upgrader.ssl, "create_default_context", return_value=sentinel) as mocked:
            ctx = self.upgrader._create_ssl_context()

        assert ctx is sentinel
        assert mocked.call_count == 1
        kwargs = mocked.call_args.kwargs
        assert kwargs.get("cafile") == os.path.abspath(str(cafile))

    def test_create_ssl_context_uses_certifi_by_default(self, monkeypatch):
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("SSL_CERT_DIR", raising=False)

        sentinel = object()
        with (
            patch("certifi.where", return_value="/tmp/certifi-ca.pem"),
            patch.object(self.upgrader.ssl, "create_default_context", return_value=sentinel) as mocked,
        ):
            ctx = self.upgrader._create_ssl_context()

        assert ctx is sentinel
        assert mocked.call_count == 1
        kwargs = mocked.call_args.kwargs
        assert kwargs.get("cafile") == "/tmp/certifi-ca.pem"

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
