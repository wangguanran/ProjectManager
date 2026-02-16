"""AI-assisted docs snippet generation with citations (optional; requires API key configuration)."""

from __future__ import annotations

import inspect
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from src.ai.llm import LLMError, load_llm_config, openai_compatible_chat
from src.log_manager import log, redact_secrets
from src.operations.registry import REGISTRY as _OP_REGISTRY
from src.operations.registry import get_registered_operations, register


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


def _read_file_excerpt(path: str, *, max_lines: int = 120) -> Tuple[str, str]:
    """Return (location, excerpt) with line numbers, redacted best-effort."""
    lines: List[str] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for idx, raw in enumerate(f, start=1):
                if idx > max_lines:
                    break
                text = raw.rstrip("\n")
                lines.append(f"{idx:>4}: {text}")
    except OSError as exc:
        return "", f"[read failed: {exc}]"
    if not lines:
        return "", "(empty)"
    location = f"L1-L{len(lines)}"
    excerpt = redact_secrets("\n".join(lines))
    return location, excerpt


def _find_markdown_section(path: str, *, needle: str, context_lines: int = 60) -> Tuple[str, str]:
    """Find a markdown section containing needle and return (location, excerpt)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw_lines = f.read().splitlines()
    except OSError as exc:
        return "", f"[read failed: {exc}]"

    hit = None
    for idx, line in enumerate(raw_lines, start=1):
        if needle in line:
            hit = idx
            break
    if hit is None:
        return "", "(no match)"

    start = max(1, hit - context_lines)
    end = min(len(raw_lines), hit + context_lines)
    excerpt_lines = [f"{i:>4}: {raw_lines[i-1]}" for i in range(start, end + 1)]
    location = f"L{start}-L{end}"
    excerpt = redact_secrets("\n".join(excerpt_lines))
    return location, excerpt


@dataclass(frozen=True)
class _Source:
    sid: str
    path: str
    location: str
    content: str


def _format_sources(sources: List[_Source]) -> str:
    parts: List[str] = []
    for s in sources:
        parts.append(f"[{s.sid}] {s.path} {s.location}".strip())
        parts.append(s.content)
        parts.append("")
    return "\n".join(parts).rstrip()


@register(
    "ai_docs",
    needs_projects=False,
    needs_repositories=False,
    desc="AI-assisted docs snippet generation with citations (requires API key).",
)
def ai_docs(
    env: Dict[str, Any],
    projects_info: Dict[str, Any],
    command: str = "",
    out: str = "",
    dry_run: bool = False,
    max_input_chars: int = 0,
    lang: str = "en",
) -> bool:
    """
    Generate a documentation snippet for a CLI command, with citations.

    command (str): Target operation name (e.g., `ai_review`, `mcp_server`).
    out (str): Optional output file path to write the snippet (also prints to stdout).
    dry_run (bool): Do not call the LLM; print the (redacted, truncated) payload that would be sent.
    max_input_chars (int): Override input size limit (defaults to env PROJMAN_LLM_MAX_INPUT_CHARS).
    lang (str): Output language (`en` or `zh`, default: `en`).
    """

    _ = projects_info

    dry_run = _truthy(dry_run)
    max_input_chars = _to_int(max_input_chars, default=0)
    lang = str(lang or "en").strip().lower()
    if lang not in {"en", "zh"}:
        print("Error: unsupported lang (use 'en' or 'zh').")
        return False

    op = str(command or "").strip()
    if not op:
        print("Error: missing command name (e.g., ai_docs ai_review).")
        return False

    # Ensure the registry has the target op (in normal CLI use, __main__ imports plugins).
    func = _OP_REGISTRY.get(op)
    if func is None:
        _ = get_registered_operations()  # side-effect: none; keeps API stable
        func = _OP_REGISTRY.get(op)
    if func is None:
        print(f"Error: unknown command: {op}")
        return False

    doc = inspect.getdoc(func) or ""
    sig = str(inspect.signature(func))
    src_file = inspect.getsourcefile(func) or ""
    try:
        _src_lines, start_line = inspect.getsourcelines(func)
        end_line = start_line + max(0, len(_src_lines) - 1)
        func_loc = f"L{start_line}-L{end_line}"
    except (OSError, TypeError):
        func_loc = ""

    root_path = env.get("root_path") or os.getcwd()
    rel_src = os.path.relpath(src_file, root_path) if src_file else "(unknown)"

    sources: List[_Source] = []
    sources.append(
        _Source(
            sid="S1",
            path=rel_src,
            location=func_loc,
            content=redact_secrets(f"Signature: {op}{sig}\n\nDocstring:\n{doc or '(no docstring)'}"),
        )
    )

    env_example = os.path.join(root_path, ".env.example")
    if os.path.exists(env_example):
        loc, excerpt = _read_file_excerpt(env_example, max_lines=120)
        sources.append(_Source(sid="S2", path=".env.example", location=loc, content=excerpt))

    # Try to include existing command reference context (helps the model match repo conventions).
    if lang == "en":
        ref = os.path.join(root_path, "docs", "en", "user-guide", "command-reference.md")
        needle = f"### `{op}`"
    else:
        ref = os.path.join(root_path, "docs", "zh", "user-guide", "command-reference.md")
        needle = f"### `{op}`"
    if os.path.exists(ref):
        loc, excerpt = _find_markdown_section(ref, needle=needle, context_lines=60)
        sources.append(_Source(sid="S3", path=os.path.relpath(ref, root_path), location=loc, content=excerpt))

    # Provide test cases context as another citation anchor.
    tc = os.path.join(root_path, "docs", "test_cases_en.md")
    if os.path.exists(tc):
        loc, excerpt = _find_markdown_section(tc, needle=op, context_lines=40)
        sources.append(_Source(sid="S4", path="docs/test_cases_en.md", location=loc, content=excerpt))

    sources_text = _format_sources(sources)

    cfg = load_llm_config(root_path=root_path)
    limit = max_input_chars or (cfg.max_input_chars if cfg else 12000)
    sources_text, truncated = _truncate(sources_text, limit=limit)

    system_en = (
        "You are writing documentation for the ProjectManager CLI.\n"
        "Use only the provided sources. Do not invent flags or behavior.\n"
        "Every factual statement must cite at least one source using [S1], [S2], ... at the end of the sentence.\n"
        "Output a markdown snippet suitable for docs/en/user-guide/command-reference.md.\n"
    )
    system_zh = (
        "你在为 ProjectManager CLI 编写文档。\n"
        "只能使用提供的 sources，不允许编造参数或行为。\n"
        "每条事实陈述句末必须至少引用一个来源标签，例如 [S1]、[S2]。\n"
        "输出适合写入 docs/zh/user-guide/command-reference.md 的 Markdown 片段。\n"
    )
    system = system_en if lang == "en" else system_zh

    user = (
        f"Generate a command reference section for `{op}`.\n"
        "Include: status, syntax, description, configuration (if any), privacy/safety notes, examples.\n"
        "If sources are insufficient, clearly state what is unknown (still cite sources for what you do know).\n\n"
        f"SOURCES:\n{sources_text}\n"
    )

    if dry_run:
        print(user)
        if truncated:
            log.warning("AI dry-run payload truncated to %d chars (override with --max-input-chars).", limit)
        return True

    if cfg is None:
        print(
            "AI is disabled: set PROJMAN_LLM_API_KEY (or OPENAI_API_KEY). "
            "Optional: PROJMAN_LLM_BASE_URL / PROJMAN_LLM_MODEL."
        )
        return False

    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    try:
        snippet = openai_compatible_chat(cfg=cfg, messages=messages)
    except LLMError as exc:
        print(f"Error: {exc}")
        return False

    snippet = redact_secrets(snippet)

    if out:
        try:
            with open(out, "w", encoding="utf-8") as f:
                f.write(snippet)
                f.write("\n")
        except OSError as exc:
            print(f"Error: failed to write output: {exc}")
            return False

    print(snippet)
    return True
