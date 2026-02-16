from __future__ import annotations

import json

import pytest


def _cfg():
    from src.ai.llm import LLMConfig

    return LLMConfig(
        api_key="dummy",
        base_url="https://example.test/v1",
        model="chat-model",
        embedding_model="embed-model",
        timeout_sec=10,
        max_input_chars=12000,
        max_output_tokens=700,
        temperature=0.2,
    )


def test_openai_compatible_embeddings_happy_path(monkeypatch) -> None:
    from src.ai import llm as llm_mod
    from src.ai.llm import openai_compatible_embeddings

    def _fake_post_json(*, url: str, headers, payload, timeout_sec: int):
        _ = (url, headers, timeout_sec)
        assert payload["model"] == "embed-model"
        assert payload["input"] == ["a", "b"]
        body = {"data": [{"index": 0, "embedding": [0.1, 0.2]}, {"index": 1, "embedding": [0.3, 0.4]}]}
        return 200, json.dumps(body)

    monkeypatch.setattr(llm_mod, "_post_json", _fake_post_json)

    out = openai_compatible_embeddings(cfg=_cfg(), inputs=["a", "b"])
    assert out == [[0.1, 0.2], [0.3, 0.4]]


def test_openai_compatible_embeddings_http_error(monkeypatch) -> None:
    from src.ai import llm as llm_mod
    from src.ai.llm import LLMError, openai_compatible_embeddings

    def _fake_post_json(*, url: str, headers, payload, timeout_sec: int):
        _ = (url, headers, payload, timeout_sec)
        return 401, '{"error":"nope"}'

    monkeypatch.setattr(llm_mod, "_post_json", _fake_post_json)

    with pytest.raises(LLMError) as exc:
        openai_compatible_embeddings(cfg=_cfg(), inputs=["x"])
    assert "HTTP 401" in str(exc.value)


def test_openai_compatible_embeddings_missing_index(monkeypatch) -> None:
    from src.ai import llm as llm_mod
    from src.ai.llm import LLMError, openai_compatible_embeddings

    def _fake_post_json(*, url: str, headers, payload, timeout_sec: int):
        _ = (url, headers, payload, timeout_sec)
        body = {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}
        return 200, json.dumps(body)

    monkeypatch.setattr(llm_mod, "_post_json", _fake_post_json)

    with pytest.raises(LLMError):
        openai_compatible_embeddings(cfg=_cfg(), inputs=["a", "b"])
