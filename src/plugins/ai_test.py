"""AI-assisted unit test scaffold generator (optional; requires API key configuration).

Safety:
- Default off (requires API key).
- Requires explicit `--allow-send-code` to send source code to the LLM.
- Sends only the selected file (never the whole repo by default).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

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


def _safe_relpath(path: str) -> str:
    path = str(path or "").strip().replace("\\", "/")
    if not path:
        return ""
    if path.startswith("/") or path.startswith("//"):
        return ""
    if ":" in path.split("/")[0]:
        return ""
    path = os.path.normpath(path).replace("\\", "/")
    if path in {"", ".", "/"}:
        return ""
    if path.startswith("..") or "/.." in path:
        return ""
    return path


def _resolve_rel_under_root(root_path: str, raw_path: str) -> str:
    """Resolve a user-supplied path to a safe workspace-relative path."""
    rel = _safe_relpath(raw_path)
    root_abs = os.path.abspath(root_path)
    if rel:
        abs_path = os.path.abspath(os.path.join(root_path, rel))
        try:
            if os.path.commonpath([abs_path, root_abs]) != root_abs:
                return ""
        except ValueError:
            return ""
        return rel

    abs_candidate = os.path.abspath(raw_path)
    try:
        if os.path.commonpath([abs_candidate, root_abs]) != root_abs:
            return ""
    except ValueError:
        return ""
    rel_from_root = os.path.relpath(abs_candidate, root_abs).replace("\\", "/")
    return _safe_relpath(rel_from_root)


def _read_text_file(abs_path: str, *, max_bytes: int) -> Tuple[bool, str]:
    try:
        if os.path.getsize(abs_path) > max_bytes:
            return False, f"file too large (> {max_bytes} bytes)"
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            return True, f.read()
    except OSError as exc:
        return False, str(exc)


@register(
    "ai_test",
    needs_projects=False,
    needs_repositories=False,
    desc="AI-assisted pytest scaffold generation (requires API key).",
)
def ai_test(
    env: Dict[str, Any],
    projects_info: Dict[str, Any],
    path: str,
    symbol: str = "",
    allow_send_code: bool = False,
    out: str = "",
    dry_run: bool = False,
    max_input_chars: int = 0,
) -> bool:
    """
    Generate pytest unit test scaffolds for a selected Python file (and optional symbol).

    path (str): Target Python file path (relative to repo root).
    symbol (str): Optional function/class name to focus on.
    allow_send_code (bool): Opt-in: send selected source code to the LLM (privacy risk).
    out (str): Optional output file path to write the generated tests (also prints to stdout).
    dry_run (bool): Do not call the LLM; print the (redacted, truncated) payload that would be sent.
    max_input_chars (int): Override input size limit (defaults to env PROJMAN_LLM_MAX_INPUT_CHARS).
    """

    _ = projects_info

    dry_run = _truthy(dry_run)
    allow_send_code = _truthy(allow_send_code)
    max_input_chars = _to_int(max_input_chars, default=0)

    root_path = env.get("root_path") or os.getcwd()

    # Only allow paths within the workspace root.
    rel = _resolve_rel_under_root(root_path, path)
    if not rel:
        print("Error: path is invalid or unsafe (must be within workspace).")
        return False

    rel_out = ""
    if out:
        rel_out = _resolve_rel_under_root(root_path, out)
        if not rel_out:
            print("Error: out path is invalid or unsafe (must be within workspace).")
            return False

    abs_path = os.path.abspath(os.path.join(root_path, rel))
    if not os.path.isfile(abs_path):
        print(f"Error: file not found: {rel}")
        return False
    if not rel.endswith(".py"):
        print("Error: only .py files are supported for ai_test.")
        return False

    # Prepare payload (redacted + size-limited).
    source_note = (
        "Source is NOT included by default. To include it, pass --allow-send-code (privacy risk)."
        if not allow_send_code
        else "Source included (opt-in)."
    )

    src_text = ""
    if allow_send_code:
        ok, content_or_err = _read_text_file(abs_path, max_bytes=200_000)
        if not ok:
            print(f"Error: failed to read source: {content_or_err}")
            return False
        src_text = redact_secrets(content_or_err)

    parts: List[str] = []
    parts.append("# Target")
    parts.append(f"path: {rel}")
    if symbol:
        parts.append(f"symbol: {redact_secrets(symbol)}")
    parts.append("")
    parts.append("# Privacy / Data Boundary")
    parts.append(source_note)
    parts.append("Generate tests without requiring network access.")
    parts.append("")
    parts.append("# Source (redacted; may be truncated)")
    parts.append(src_text if src_text else "(omitted)")
    payload = "\n".join(parts)

    cfg = load_llm_config(root_path=root_path)
    limit = max_input_chars or (cfg.max_input_chars if cfg else 12000)
    payload, truncated = _truncate(payload, limit=limit)

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

    if not allow_send_code:
        print("Error: refusing to send source code by default. Re-run with --allow-send-code to opt in.")
        return False

    system = (
        "You are a staff-level Python engineer.\n"
        "Generate pytest unit tests for the given source file and optional symbol.\n"
        "Constraints:\n"
        "- Output ONLY valid Python code (no markdown, no commentary).\n"
        "- Tests must be deterministic and not require network access.\n"
        "- Prefer unit tests with minimal mocking.\n"
        "- If you need assumptions, encode them as TODO comments in the test file.\n"
    )
    user = (
        "Create pytest tests for the target.\n"
        "Return a single Python file content (suitable for tests/).\n\n"
        f"{payload}"
    )

    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    try:
        out = openai_compatible_chat(cfg=cfg, messages=messages)
    except LLMError as exc:
        print(f"Error: {exc}")
        return False

    # Never log the generated content; only log safe metadata.
    log.info("ai_test generated output for %s (len=%d)", rel, len(out))
    out_text = out.strip() + "\n"

    if rel_out:
        abs_out = os.path.abspath(os.path.join(root_path, rel_out))
        try:
            os.makedirs(os.path.dirname(abs_out), exist_ok=True)
            with open(abs_out, "w", encoding="utf-8") as f:
                f.write(out_text)
        except OSError as exc:
            print(f"Error: failed to write output: {exc}")
            return False
        print(f"Wrote: {rel_out}")
        print(f"Verify: pytest -q {rel_out}")
        print("")

    print(out_text)
    return True
