from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict


def _init_git_repo(repo_dir: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_dir), check=True)

    (repo_dir / "a.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=str(repo_dir), check=True)


def test_ai_review_dry_run_no_key(tmp_path: Path, capsys, monkeypatch) -> None:
    from src.plugins.ai_review import ai_review

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _init_git_repo(repo_dir)

    # Create a working tree change
    (repo_dir / "a.txt").write_text("base\nchange\n", encoding="utf-8")

    # Ensure no ambient key is used
    monkeypatch.delenv("PROJMAN_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    env: Dict[str, Any] = {"root_path": str(repo_dir), "projects_path": str(repo_dir / "projects")}
    ok = ai_review(env, {}, dry_run=True)
    assert ok is True

    out = capsys.readouterr().out
    assert "## Git diff --stat" in out
    assert "a.txt" in out
    assert "## Git diff (full" not in out


def test_ai_review_missing_key_errors(tmp_path: Path, capsys, monkeypatch) -> None:
    from src.plugins.ai_review import ai_review

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _init_git_repo(repo_dir)

    (repo_dir / "a.txt").write_text("base\nchange\n", encoding="utf-8")

    monkeypatch.delenv("PROJMAN_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    env: Dict[str, Any] = {"root_path": str(repo_dir), "projects_path": str(repo_dir / "projects")}
    ok = ai_review(env, {}, dry_run=False)
    assert ok is False
    assert "AI is disabled" in capsys.readouterr().out


def test_ai_review_mock_provider_happy_path(tmp_path: Path, capsys, monkeypatch) -> None:
    from src.ai import llm as llm_mod
    from src.plugins.ai_review import ai_review

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _init_git_repo(repo_dir)
    (repo_dir / "a.txt").write_text("base\nchange\n", encoding="utf-8")

    monkeypatch.setenv("PROJMAN_LLM_API_KEY", "dummy")
    monkeypatch.setenv("PROJMAN_LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("PROJMAN_LLM_MODEL", "test-model")

    captured = {}

    def _fake_post_json(*, url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout_sec: int):
        _ = (url, headers, timeout_sec)
        captured["payload"] = payload
        return 200, json.dumps({"choices": [{"message": {"content": "OK REVIEW"}}]})

    monkeypatch.setattr(llm_mod, "_post_json", _fake_post_json)

    env: Dict[str, Any] = {"root_path": str(repo_dir), "projects_path": str(repo_dir / "projects")}
    ok = ai_review(env, {}, dry_run=False)
    assert ok is True

    out = capsys.readouterr().out
    assert "OK REVIEW" in out

    # Default behavior: do not send full diff unless explicitly opted in.
    msgs = captured["payload"]["messages"]
    assert "## Git diff (full" not in msgs[1]["content"]
