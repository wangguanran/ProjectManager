"""Tests for build info generation helpers."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest.mock import patch


def _load_write_build_info_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "write_build_info.py"
    spec = importlib.util.spec_from_file_location("write_build_info", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_resolve_release_channel_prefers_explicit_env(tmp_path: Path) -> None:
    mod = _load_write_build_info_module()
    with patch.dict(os.environ, {"PROJMAN_RELEASE_CHANNEL": "stable"}, clear=False):
        with patch.object(mod, "_has_stable_tag", return_value=False):
            assert mod._resolve_release_channel(tmp_path) == "stable"


def test_resolve_release_channel_uses_release_tag(tmp_path: Path) -> None:
    mod = _load_write_build_info_module()
    env = {
        "GITHUB_REF": "refs/tags/v0.0.17",
        "GITHUB_REF_TYPE": "tag",
    }
    with patch.dict(os.environ, env, clear=True):
        assert mod._resolve_release_channel(tmp_path) == "stable"


def test_resolve_release_channel_defaults_to_beta_for_untagged_build(tmp_path: Path) -> None:
    mod = _load_write_build_info_module()
    with patch.dict(os.environ, {}, clear=True):
        with patch.object(mod, "_has_stable_tag", return_value=False):
            assert mod._resolve_release_channel(tmp_path) == "beta"
