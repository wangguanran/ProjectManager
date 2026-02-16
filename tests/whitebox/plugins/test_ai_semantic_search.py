from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def test_ai_index_dry_run_no_key(tmp_path: Path, capsys, monkeypatch) -> None:
    from src.plugins.ai_semantic_search import ai_index

    (tmp_path / "README.md").write_text("Hello docs\n", encoding="utf-8")

    monkeypatch.delenv("PROJMAN_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_index(env, {}, dry_run=True)
    assert ok is True

    out = capsys.readouterr().out
    assert "Index plan:" in out
    assert "README.md" in out


def test_ai_index_missing_key_errors(tmp_path: Path, capsys, monkeypatch) -> None:
    from src.plugins.ai_semantic_search import ai_index

    (tmp_path / "README.md").write_text("Hello docs\n", encoding="utf-8")

    monkeypatch.delenv("PROJMAN_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_index(env, {}, dry_run=False)
    assert ok is False
    assert "AI is disabled" in capsys.readouterr().out


def test_ai_index_mock_embeddings_writes_index_and_redacts(tmp_path: Path, monkeypatch) -> None:
    from src.ai import llm as llm_mod
    from src.plugins.ai_semantic_search import ai_index

    token = "ghp_" + ("A" * 36)
    (tmp_path / "README.md").write_text(f"Intro\n{token}\n", encoding="utf-8")

    monkeypatch.setenv("PROJMAN_LLM_API_KEY", "dummy")
    monkeypatch.setenv("PROJMAN_LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("PROJMAN_LLM_MODEL", "test-model")
    monkeypatch.setenv("PROJMAN_LLM_EMBEDDING_MODEL", "test-embed")

    def _fake_post_json(*, url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout_sec: int):
        _ = (headers, timeout_sec)
        assert url.endswith("/embeddings")
        assert payload["model"] == "test-embed"
        # Ensure raw token is not sent.
        assert token not in payload["input"][0]
        return 200, json.dumps({"data": [{"index": 0, "embedding": [1.0, 0.0]}]})

    monkeypatch.setattr(llm_mod, "_post_json", _fake_post_json)

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_index(env, {}, dry_run=False, max_files=5, max_chunks=1)
    assert ok is True

    index_path = tmp_path / ".cache" / "ai_index" / "semantic_index.json"
    assert index_path.exists()

    data = json.loads(index_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["embedding_model"] == "test-embed"
    assert data["chunks_indexed"] == 1
    assert data["chunks"][0]["embedding"] == [1.0, 0.0]
    # Stored snippet must be redacted.
    assert token not in data["chunks"][0]["text"]


def test_ai_search_top_match(tmp_path: Path, capsys, monkeypatch) -> None:
    from src.ai import llm as llm_mod
    from src.plugins.ai_semantic_search import ai_search

    # Prepare a minimal index file with deterministic embeddings.
    idx_dir = tmp_path / ".cache" / "ai_index"
    idx_dir.mkdir(parents=True)
    (idx_dir / "semantic_index.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "root": ".",
                "embedding_model": "test-embed",
                "allow_send_code": False,
                "files_indexed": 1,
                "chunks_indexed": 2,
                "chunks": [
                    {"path": "docs/a.md", "start_line": 1, "end_line": 2, "text": "alpha", "embedding": [1.0, 0.0]},
                    {"path": "docs/b.md", "start_line": 1, "end_line": 2, "text": "beta", "embedding": [0.0, 1.0]},
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("PROJMAN_LLM_API_KEY", "dummy")
    monkeypatch.setenv("PROJMAN_LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("PROJMAN_LLM_MODEL", "test-model")
    monkeypatch.setenv("PROJMAN_LLM_EMBEDDING_MODEL", "test-embed")

    def _fake_post_json(*, url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout_sec: int):
        _ = (headers, timeout_sec)
        assert url.endswith("/embeddings")
        assert payload["model"] == "test-embed"
        # Query embedding should be closest to docs/a.md
        return 200, json.dumps({"data": [{"index": 0, "embedding": [0.9, 0.1]}]})

    monkeypatch.setattr(llm_mod, "_post_json", _fake_post_json)

    env: Dict[str, Any] = {"root_path": str(tmp_path), "projects_path": str(tmp_path / "projects")}
    ok = ai_search(env, {}, query="alpha", top_k=1)
    assert ok is True

    out = capsys.readouterr().out
    assert "docs/a.md" in out
