from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def test_ai_test_dry_run_no_key(tmp_path: Path, capsys, monkeypatch) -> None:
    from src.plugins.ai_test import ai_test

    (tmp_path / "mod.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    monkeypatch.delenv("PROJMAN_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_test(env, {}, "mod.py", dry_run=True)
    assert ok is True

    out = capsys.readouterr().out
    assert "path: mod.py" in out
    assert "Source (redacted" in out


def test_ai_test_missing_key_errors(tmp_path: Path, capsys, monkeypatch) -> None:
    from src.plugins.ai_test import ai_test

    (tmp_path / "mod.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    monkeypatch.delenv("PROJMAN_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_test(env, {}, "mod.py", allow_send_code=True, dry_run=False)
    assert ok is False
    assert "AI is disabled" in capsys.readouterr().out


def test_ai_test_requires_allow_send_code(tmp_path: Path, capsys, monkeypatch) -> None:
    from src.plugins.ai_test import ai_test

    (tmp_path / "mod.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    monkeypatch.setenv("PROJMAN_LLM_API_KEY", "dummy")
    monkeypatch.setenv("PROJMAN_LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("PROJMAN_LLM_MODEL", "test-model")

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_test(env, {}, "mod.py", allow_send_code=False, dry_run=False)
    assert ok is False
    assert "--allow-send-code" in capsys.readouterr().out


def test_ai_test_mock_provider_happy_path(tmp_path: Path, capsys, monkeypatch) -> None:
    from src.ai import llm as llm_mod
    from src.plugins.ai_test import ai_test

    token = "ghp_" + ("A" * 36)
    (tmp_path / "mod.py").write_text(f"def add(a, b):\n    return a + b  # {token}\n", encoding="utf-8")

    monkeypatch.setenv("PROJMAN_LLM_API_KEY", "dummy")
    monkeypatch.setenv("PROJMAN_LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("PROJMAN_LLM_MODEL", "test-model")

    def _fake_post_json(*, url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout_sec: int):
        _ = (headers, timeout_sec)
        assert url.endswith("/chat/completions")
        # Raw token must not be sent.
        assert token not in json.dumps(payload)
        return 200, json.dumps({"choices": [{"message": {"content": "def test_smoke():\\n    assert True\\n"}}]})

    monkeypatch.setattr(llm_mod, "_post_json", _fake_post_json)

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_test(env, {}, "mod.py", allow_send_code=True, dry_run=False)
    assert ok is True
    assert "def test_smoke" in capsys.readouterr().out


def test_ai_test_out_path_unsafe_rejected(tmp_path: Path, capsys) -> None:
    from src.plugins.ai_test import ai_test

    (tmp_path / "mod.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_test(env, {}, "mod.py", out="../bad.py", dry_run=True)
    assert ok is False
    assert "out path is invalid" in capsys.readouterr().out


def test_ai_test_writes_out_with_mock_provider(tmp_path: Path, capsys, monkeypatch) -> None:
    from src.ai import llm as llm_mod
    from src.plugins.ai_test import ai_test

    (tmp_path / "mod.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    monkeypatch.setenv("PROJMAN_LLM_API_KEY", "dummy")
    monkeypatch.setenv("PROJMAN_LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("PROJMAN_LLM_MODEL", "test-model")

    def _fake_post_json(*, url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout_sec: int):
        _ = (url, headers, payload, timeout_sec)
        return 200, json.dumps({"choices": [{"message": {"content": "def test_smoke():\\n    assert True\\n"}}]})

    monkeypatch.setattr(llm_mod, "_post_json", _fake_post_json)

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_test(env, {}, "mod.py", allow_send_code=True, out="tests/test_generated.py")
    assert ok is True

    out_path = tmp_path / "tests" / "test_generated.py"
    assert out_path.exists()
    assert "def test_smoke" in out_path.read_text(encoding="utf-8")
    assert "Wrote: tests/test_generated.py" in capsys.readouterr().out
