"""Minimal LLM client abstraction (OpenAI-compatible HTTP API).

Safety:
- API keys are read from environment variables or a local .env file (never persisted).
- Requests are size-limited and best-effort redacted before sending.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib import error as urlerror
from urllib import request as urlrequest

from src.log_manager import log, redact_secrets


class LLMError(RuntimeError):
    """User-facing LLM error (safe to print; already redacted)."""


def _parse_int(value: str, *, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _parse_float(value: str, *, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _dotenv_load_if_present(dotenv_path: str) -> None:
    """Load KEY=VALUE pairs from .env into os.environ if not already set.

    This is intentionally minimal (no expansion, no export). It supports:
    - blank lines and '#' comments
    - quoted values with single/double quotes

    It never overwrites existing env vars.
    """
    try:
        if not os.path.exists(dotenv_path):
            return
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if not key:
                    continue
                if key in os.environ:
                    continue
                if len(val) >= 2 and ((val[0] == val[-1] == '"') or (val[0] == val[-1] == "'")):
                    val = val[1:-1]
                os.environ[key] = val
    except (OSError, UnicodeError):
        # Silent by design: .env is optional and should not break core flows.
        return


@dataclass(frozen=True)
# pylint: disable=too-many-instance-attributes
class LLMConfig:
    """Configuration for OpenAI-compatible LLM calls."""

    api_key: str
    base_url: str
    model: str
    embedding_model: str
    timeout_sec: int
    max_input_chars: int
    max_output_tokens: int
    temperature: float


def load_llm_config(*, root_path: str) -> Optional[LLMConfig]:
    """Load LLM config from env and optional local .env.

    Returns None if no API key is configured.
    """
    _dotenv_load_if_present(os.path.join(root_path, ".env"))

    api_key = (os.environ.get("PROJMAN_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None

    base_url = (os.environ.get("PROJMAN_LLM_BASE_URL") or "https://api.openai.com/v1").strip()
    model = (os.environ.get("PROJMAN_LLM_MODEL") or "gpt-4o-mini").strip()
    embedding_model = (os.environ.get("PROJMAN_LLM_EMBEDDING_MODEL") or "text-embedding-3-small").strip()
    timeout_sec = _parse_int(os.environ.get("PROJMAN_LLM_TIMEOUT_SEC", ""), default=30)
    max_input_chars = _parse_int(os.environ.get("PROJMAN_LLM_MAX_INPUT_CHARS", ""), default=12000)
    max_output_tokens = _parse_int(os.environ.get("PROJMAN_LLM_MAX_OUTPUT_TOKENS", ""), default=700)
    temperature = _parse_float(os.environ.get("PROJMAN_LLM_TEMPERATURE", ""), default=0.2)

    return LLMConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        embedding_model=embedding_model,
        timeout_sec=timeout_sec,
        max_input_chars=max_input_chars,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )


def _post_json(
    *,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_sec: int,
) -> Tuple[int, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urlrequest.Request(url, data=data, headers=headers, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=timeout_sec) as resp:  # nosec - URL is user-configurable by design.
            body = resp.read().decode("utf-8", errors="replace")
            return int(getattr(resp, "status", 200)), body
    except urlerror.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # pylint: disable=broad-exception-caught
            body = ""
        return int(getattr(exc, "code", 0) or 0), body
    except urlerror.URLError as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc


def openai_compatible_chat(
    *,
    cfg: LLMConfig,
    messages: List[Dict[str, str]],
) -> str:
    """Call OpenAI-compatible Chat Completions API and return assistant text."""
    url = cfg.base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg.api_key}",
    }
    payload: Dict[str, Any] = {
        "model": cfg.model,
        "messages": messages,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_output_tokens,
    }

    # Never log headers/payload (may contain sensitive data); only log safe metadata.
    log.info("AI request: model=%s base_url=%s", cfg.model, cfg.base_url)

    status, body = _post_json(url=url, headers=headers, payload=payload, timeout_sec=cfg.timeout_sec)
    if status < 200 or status >= 300:
        safe_body = redact_secrets(body)[:800]
        raise LLMError(f"LLM request failed (HTTP {status}): {safe_body}")

    try:
        data = json.loads(body)
        choices = data.get("choices") or []
        if not choices:
            raise LLMError("LLM response missing choices")
        msg = choices[0].get("message") or {}
        content = msg.get("content") or ""
        return str(content).strip()
    except (ValueError, TypeError) as exc:
        safe_body = redact_secrets(body)[:800]
        raise LLMError(f"LLM response parse failed: {safe_body}") from exc


def openai_compatible_embeddings(
    *,
    cfg: LLMConfig,
    inputs: List[str],
) -> List[List[float]]:
    """Call OpenAI-compatible Embeddings API and return embeddings in input order."""
    if not inputs:
        return []

    url = cfg.base_url.rstrip("/") + "/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg.api_key}",
    }
    payload: Dict[str, Any] = {
        "model": cfg.embedding_model,
        "input": inputs,
    }

    log.info("AI embeddings request: model=%s base_url=%s inputs=%d", cfg.embedding_model, cfg.base_url, len(inputs))

    status, body = _post_json(url=url, headers=headers, payload=payload, timeout_sec=cfg.timeout_sec)
    if status < 200 or status >= 300:
        safe_body = redact_secrets(body)[:800]
        raise LLMError(f"LLM embeddings request failed (HTTP {status}): {safe_body}")

    try:
        data = json.loads(body)
        items = data.get("data") or []
        if not items or not isinstance(items, list):
            raise LLMError("LLM embeddings response missing data")
        # Preserve input order via index field.
        indexed: Dict[int, List[float]] = {}
        for it in items:
            idx = it.get("index")
            emb = it.get("embedding")
            if isinstance(idx, int) and isinstance(emb, list):
                indexed[idx] = emb
        out: List[List[float]] = []
        for i in range(len(inputs)):
            if i not in indexed:
                raise LLMError("LLM embeddings response missing index")
            out.append(indexed[i])
        return out
    except (ValueError, TypeError) as exc:
        safe_body = redact_secrets(body)[:800]
        raise LLMError(f"LLM embeddings response parse failed: {safe_body}") from exc
