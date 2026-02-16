"""AI-assisted review commands (optional; requires API key configuration)."""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from src.ai.llm import LLMError, load_llm_config, openai_compatible_chat
from src.log_manager import log, redact_secrets
from src.operations.registry import register


def _run_git(args: List[str], *, cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def _ensure_git_repo(repo_dir: str) -> Tuple[bool, str]:
    result = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=repo_dir)
    ok = result.returncode == 0 and result.stdout.strip().lower() == "true"
    if ok:
        return True, ""
    msg = (result.stderr or result.stdout or "").strip()
    if not msg:
        msg = "not a git repository"
    return False, msg


def _git_text(repo_dir: str, *, staged: bool, diff: bool) -> Tuple[str, str, str]:
    """Return (status_porcelain, diff_stat, diff_text_or_empty)."""
    status = _run_git(["status", "--porcelain"], cwd=repo_dir)
    status_text = (status.stdout or "").strip()

    stat_args = ["diff", "--stat", "--no-color"]
    diff_args = ["diff", "--no-color"]
    if staged:
        stat_args.insert(1, "--cached")
        diff_args.insert(1, "--cached")

    stat = _run_git(stat_args, cwd=repo_dir)
    stat_text = (stat.stdout or "").strip()

    diff_text = ""
    if diff:
        d = _run_git(diff_args, cwd=repo_dir)
        diff_text = (d.stdout or "").strip()
    return status_text, stat_text, diff_text


def _truncate(text: str, *, limit: int) -> Tuple[str, bool]:
    if limit <= 0 or len(text) <= limit:
        return text, False
    return text[:limit] + "\n[TRUNCATED]\n", True


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


@register(
    "ai_review",
    needs_projects=False,
    needs_repositories=False,
    desc="AI-assisted review of git changes (requires API key).",
)
def ai_review(
    env: Dict[str, Any],
    projects_info: Dict[str, Any],
    repo: str = ".",
    staged: bool = False,
    allow_send_diff: bool = False,
    out: str = "",
    dry_run: bool = False,
    max_input_chars: int = 0,
) -> bool:
    """
    Generate an AI-assisted review for the current git changes.

    repo (str): Path to a git repository to review (default: current directory).
    staged (bool): Review staged changes only (`git diff --cached`).
    allow_send_diff (bool): Opt-in: send full diff content to the LLM (privacy risk).
    out (str): Optional output file path to write the review (also prints to stdout).
    dry_run (bool): Do not call the LLM; print the (redacted, truncated) payload that would be sent.
    max_input_chars (int): Override input size limit (defaults to env PROJMAN_LLM_MAX_INPUT_CHARS).
    """

    _ = projects_info

    staged = _truthy(staged)
    allow_send_diff = _truthy(allow_send_diff)
    dry_run = _truthy(dry_run)
    max_input_chars = _to_int(max_input_chars, default=0)

    root_path = env.get("root_path") or os.getcwd()
    repo_dir = repo
    if not os.path.isabs(repo_dir):
        repo_dir = os.path.join(root_path, repo_dir)
    repo_dir = os.path.abspath(repo_dir)

    ok, err = _ensure_git_repo(repo_dir)
    if not ok:
        print(f"Error: {err}")
        return False

    status_text, stat_text, diff_text = _git_text(repo_dir, staged=staged, diff=allow_send_diff)

    # Minimal-by-default: only send stat + file list unless explicitly opted-in for full diff.
    payload_parts: List[str] = []
    payload_parts.append("## Git status (porcelain)")
    payload_parts.append(status_text or "(clean)")
    payload_parts.append("")
    payload_parts.append("## Git diff --stat")
    payload_parts.append(stat_text or "(no changes)")
    if allow_send_diff:
        payload_parts.append("")
        payload_parts.append("## Git diff (full; may be truncated)")
        payload_parts.append(diff_text or "(empty)")

    payload = "\n".join(payload_parts)
    payload = redact_secrets(payload)

    cfg = load_llm_config(root_path=repo_dir)
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

    system = (
        "You are a staff-level software engineer. Review the given git change summary and optionally diff.\n"
        "Output a concise review with: summary, risks (security/correctness/performance), and suggested tests.\n"
        "If the input is only --stat (no diff), be explicit about uncertainty."
    )
    user = "Review the following changes.\n" "Privacy note: do not ask for more code unless necessary.\n\n" f"{payload}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    try:
        review = openai_compatible_chat(cfg=cfg, messages=messages)
    except LLMError as exc:
        print(f"Error: {exc}")
        return False

    if out:
        try:
            with open(out, "w", encoding="utf-8") as f:
                f.write(review)
                f.write("\n")
        except OSError as exc:
            print(f"Error: failed to write output: {exc}")
            return False

    print(review)
    return True
