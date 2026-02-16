"""AI-assisted debugging for logs / CI failures (optional; requires API key configuration)."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from src.ai.llm import LLMError, load_llm_config, openai_compatible_chat
from src.log_manager import log, redact_secrets
from src.operations.registry import register


def _truthy(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    text = str(val).strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _to_int(val: Any, *, default: int) -> int:
    if isinstance(val, int):
        return val
    try:
        return int(str(val).strip())
    except (TypeError, ValueError):
        return default


def _truncate(text: str, *, limit: int) -> Tuple[str, bool]:
    if limit <= 0 or len(text) <= limit:
        return text, False
    return text[:limit] + "\n[TRUNCATED]\n", True


def _read_file_tail(
    path: str,
    *,
    tail_lines: int,
    max_bytes: int,
) -> Tuple[str, bool]:
    """Read a tail excerpt from a text file.

    Returns: (text, truncated_by_bytes).
    """
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = int(f.tell())
        read_size = min(size, int(max_bytes))
        f.seek(max(0, size - read_size), os.SEEK_SET)
        data = f.read(read_size)

    truncated = read_size < size
    text = data.decode("utf-8", errors="replace")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    if tail_lines > 0:
        lines = lines[-int(tail_lines) :]
    out = "\n".join(lines).strip()
    return out, truncated


@register(
    "ai_explain",
    needs_projects=False,
    needs_repositories=False,
    desc="AI-assisted explanation of logs/CI failures (requires API key).",
)
def ai_explain(
    env: Dict[str, Any],
    projects_info: Dict[str, Any],
    path: str = "",
    tail_lines: int = 200,
    out: str = "",
    dry_run: bool = False,
    max_input_chars: int = 0,
    question: str = "",
) -> bool:
    """
    Explain logs / CI failures using an LLM.

    path (str): Path to a log file to analyze. Default: `.cache/latest.log` under repo root.
    tail_lines (int): How many lines from the end to include (default: 200).
    out (str): Optional output file path to write the analysis (also prints to stdout).
    dry_run (bool): Do not call the LLM; print the (redacted, truncated) payload that would be sent.
    max_input_chars (int): Override input size limit (defaults to env PROJMAN_LLM_MAX_INPUT_CHARS).
    question (str): Optional user question to guide the analysis.
    """

    _ = projects_info

    dry_run = _truthy(dry_run)
    tail_lines = _to_int(tail_lines, default=200)
    max_input_chars = _to_int(max_input_chars, default=0)
    question = str(question or "").strip()

    root_path = env.get("root_path") or os.getcwd()
    log_path = path.strip() if isinstance(path, str) else ""
    if not log_path:
        log_path = os.path.join(root_path, ".cache", "latest.log")
    if not os.path.isabs(log_path):
        log_path = os.path.abspath(os.path.join(root_path, log_path))

    if not os.path.isfile(log_path):
        print(f"Error: log file not found: {log_path}")
        return False

    try:
        excerpt, truncated_by_bytes = _read_file_tail(log_path, tail_lines=tail_lines, max_bytes=600_000)
    except OSError as exc:
        print(f"Error: failed to read log: {exc}")
        return False

    excerpt = redact_secrets(excerpt)

    cfg = load_llm_config(root_path=root_path)
    limit = max_input_chars or (cfg.max_input_chars if cfg else 12000)
    excerpt, truncated = _truncate(excerpt, limit=limit)

    payload = "\n".join(
        [
            f"# Log excerpt ({os.path.relpath(log_path, root_path)})",
            f"- tail_lines={tail_lines}",
            f"- truncated_by_bytes={truncated_by_bytes}",
            f"- truncated_by_chars={truncated}",
            "",
            excerpt or "(empty)",
        ]
    )

    if dry_run:
        print(payload)
        if truncated:
            log.warning("AI dry-run payload truncated to %d chars (override with --max-input-chars).", limit)
        return True

    if cfg is None:
        print(
            "AI is disabled: set PROJMAN_LLM_API_KEY (or OPENAI_API_KEY). "
            "Optional: PROJMAN_LLM_BASE_URL / PROJMAN_LLM_MODEL."
        )
        return False

    system = (
        "You are a staff-level software engineer. Analyze the given ProjectManager logs/CI excerpt.\n"
        "Output: (1) likely root cause(s), (2) what to try next (commands/checks), (3) how to confirm the fix.\n"
        "Be explicit about uncertainty when evidence is insufficient. Do not request more code unless necessary."
    )
    user = "Explain the following failure.\n\n"
    if question:
        user += f"User question: {question}\n\n"
    user += payload
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    try:
        analysis = openai_compatible_chat(cfg=cfg, messages=messages)
    except LLMError as exc:
        print(f"Error: {exc}")
        return False

    analysis = redact_secrets(analysis)

    if out:
        try:
            with open(out, "w", encoding="utf-8") as f:
                f.write(analysis)
                f.write("\n")
        except OSError as exc:
            print(f"Error: failed to write output: {exc}")
            return False

    print(analysis)
    return True
