from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def test_ai_explain_dry_run_redacts_without_key(tmp_path: Path, capsys, monkeypatch) -> None:
    from src.plugins.ai_explain import ai_explain

    (tmp_path / ".cache").mkdir()
    token = "ghp_" + ("A" * 36)
    (tmp_path / ".cache" / "latest.log").write_text(f"start\n{token}\nBearer xyz\nend\n", encoding="utf-8")

    monkeypatch.delenv("PROJMAN_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_explain(env, {}, dry_run=True)
    assert ok is True

    out = capsys.readouterr().out
    assert "# Log excerpt" in out
    assert token not in out
    assert "ghp_***" in out
    assert "Bearer ***" in out


def test_ai_explain_missing_key_errors(tmp_path: Path, capsys, monkeypatch) -> None:
    from src.plugins.ai_explain import ai_explain

    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache" / "latest.log").write_text("x\n", encoding="utf-8")

    monkeypatch.delenv("PROJMAN_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_explain(env, {}, dry_run=False)
    assert ok is False
    assert "AI is disabled" in capsys.readouterr().out


def test_ai_explain_mock_provider_happy_path(tmp_path: Path, capsys, monkeypatch) -> None:
    from src.ai import llm as llm_mod
    from src.plugins.ai_explain import ai_explain

    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache" / "latest.log").write_text("boom\n", encoding="utf-8")

    monkeypatch.setenv("PROJMAN_LLM_API_KEY", "dummy")
    monkeypatch.setenv("PROJMAN_LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("PROJMAN_LLM_MODEL", "test-model")

    def _fake_post_json(*, url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout_sec: int):
        _ = (url, headers, timeout_sec)
        assert payload["messages"][1]["content"].startswith("Explain the following failure.")
        return 200, json.dumps({"choices": [{"message": {"content": "OK EXPLAIN"}}]})

    monkeypatch.setattr(llm_mod, "_post_json", _fake_post_json)

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_explain(env, {}, dry_run=False)
    assert ok is True
    assert "OK EXPLAIN" in capsys.readouterr().out
