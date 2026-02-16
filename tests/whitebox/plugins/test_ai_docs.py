from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def test_ai_docs_dry_run_no_key(tmp_path: Path, capsys, monkeypatch) -> None:
    # Ensure target command is registered.
    import src.plugins.ai_review  # noqa: F401
    from src.plugins.ai_docs import ai_docs

    monkeypatch.delenv("PROJMAN_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_docs(env, {}, command="ai_review", dry_run=True)
    assert ok is True

    out = capsys.readouterr().out
    assert "SOURCES:" in out
    assert "[S1]" in out
    assert "Signature:" in out


def test_ai_docs_missing_key_errors(tmp_path: Path, capsys, monkeypatch) -> None:
    import src.plugins.ai_review  # noqa: F401
    from src.plugins.ai_docs import ai_docs

    monkeypatch.delenv("PROJMAN_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_docs(env, {}, command="ai_review", dry_run=False)
    assert ok is False
    assert "AI is disabled" in capsys.readouterr().out


def test_ai_docs_mock_provider_happy_path(tmp_path: Path, capsys, monkeypatch) -> None:
    import src.plugins.ai_review  # noqa: F401
    from src.ai import llm as llm_mod
    from src.plugins.ai_docs import ai_docs

    # Provide a minimal env root with an .env.example to include as a source.
    (tmp_path / ".env.example").write_text("PROJMAN_LLM_API_KEY=your_key\n", encoding="utf-8")

    monkeypatch.setenv("PROJMAN_LLM_API_KEY", "dummy")
    monkeypatch.setenv("PROJMAN_LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("PROJMAN_LLM_MODEL", "test-model")

    def _fake_post_json(*, url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout_sec: int):
        _ = (url, headers, timeout_sec)
        # Ensure citations instruction exists.
        assert "[S1]" in payload["messages"][1]["content"]
        return 200, json.dumps({"choices": [{"message": {"content": "OK DOCS"}}]})

    monkeypatch.setattr(llm_mod, "_post_json", _fake_post_json)

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_docs(env, {}, command="ai_review", dry_run=False, lang="en")
    assert ok is True
    assert "OK DOCS" in capsys.readouterr().out
