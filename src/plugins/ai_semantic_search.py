"""Semantic search over docs/code using embeddings (optional; requires API key configuration).

Safety:
- Default indexes docs only. Indexing source code requires explicit opt-in.
- Index is stored under .cache/ (gitignored by default).
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.ai.llm import LLMError, load_llm_config, openai_compatible_embeddings
from src.log_manager import log, redact_secrets
from src.operations.registry import register

_INDEX_DIR = os.path.join(".cache", "ai_index")
_INDEX_FILE = os.path.join(_INDEX_DIR, "semantic_index.json")
_SCHEMA_VERSION = 1

_EXCLUDE_DIRS = {
    ".git",
    ".cache",
    ".agent_artifacts",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}

_EXCLUDE_FILES = {
    ".env",
    ".env.local",
    ".envrc",
}


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


def _is_excluded(relpath: str) -> bool:
    parts = relpath.split("/") if relpath else []
    if parts and parts[0] in _EXCLUDE_DIRS:
        return True
    if parts and parts[-1] in _EXCLUDE_FILES:
        return True
    return False


def _iter_files(root_dir: str, *, rel_roots: List[str], exts: List[str], max_files: int) -> Iterable[str]:
    count = 0
    for rel_root in rel_roots:
        base = os.path.join(root_dir, rel_root) if rel_root else root_dir
        if not os.path.exists(base):
            continue
        if os.path.isfile(base):
            rel = rel_root
            if rel and not _is_excluded(rel) and any(rel.endswith(e) for e in exts):
                yield rel
                count += 1
                if count >= max_files:
                    return
            continue

        for dirpath, dirnames, filenames in os.walk(base):
            rel_dir = os.path.relpath(dirpath, root_dir).replace("\\", "/")
            rel_dir = "" if rel_dir == "." else rel_dir

            keep = []
            for d in dirnames:
                rel = f"{rel_dir}/{d}" if rel_dir else d
                if _is_excluded(rel):
                    continue
                keep.append(d)
            dirnames[:] = keep

            for fn in sorted(filenames):
                rel = f"{rel_dir}/{fn}" if rel_dir else fn
                rel = rel.replace("\\", "/")
                if _is_excluded(rel):
                    continue
                if not any(rel.endswith(e) for e in exts):
                    continue
                yield rel
                count += 1
                if count >= max_files:
                    return


@dataclass(frozen=True)
class _Chunk:
    path: str
    start_line: int
    end_line: int
    text: str


def _chunk_text(path: str, content: str, *, max_lines: int, max_chars: int) -> List[_Chunk]:
    lines = content.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    chunks: List[_Chunk] = []
    buf: List[str] = []
    start = 1
    cur_chars = 0
    cur_lines = 0

    def flush(end_line: int) -> None:
        nonlocal buf, start, cur_chars, cur_lines
        if not buf:
            return
        text = "\n".join(buf).strip()
        if text:
            chunks.append(_Chunk(path=path, start_line=start, end_line=end_line, text=text))
        buf = []
        start = end_line + 1
        cur_chars = 0
        cur_lines = 0

    for idx, line in enumerate(lines, start=1):
        buf.append(line)
        cur_lines += 1
        cur_chars += len(line) + 1
        if cur_lines >= max_lines or cur_chars >= max_chars:
            flush(idx)
    flush(len(lines))
    return chunks


def _cosine(a: List[float], b: List[float]) -> float:
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += float(x) * float(y)
        na += float(x) * float(x)
        nb += float(y) * float(y)
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _index_abs_path(root_dir: str) -> str:
    return os.path.join(root_dir, _INDEX_FILE)


@register(
    "ai_index",
    needs_projects=False,
    needs_repositories=False,
    desc="Build semantic search index under .cache (requires API key).",
)
def ai_index(
    env: Dict[str, Any],
    projects_info: Dict[str, Any],
    allow_send_code: bool = False,
    dry_run: bool = False,
    max_files: int = 200,
    max_chunks: int = 200,
) -> bool:
    """
    Build a semantic search index under `.cache/ai_index/semantic_index.json`.

    allow_send_code (bool): Opt-in: index source code files (privacy/cost risk). Default: docs-only.
    dry_run (bool): Do not call embeddings API; print what would be indexed.
    max_files (int): Maximum number of files to index.
    max_chunks (int): Maximum number of chunks to embed.
    """

    _ = projects_info

    allow_send_code = _truthy(allow_send_code)
    dry_run = _truthy(dry_run)
    max_files = _to_int(max_files, default=200)
    max_chunks = _to_int(max_chunks, default=500)

    root_dir = env.get("root_path") or os.getcwd()

    rel_roots = ["README.md", "docs"]
    exts = [".md"]
    if allow_send_code:
        rel_roots.extend(["src", "tests"])
        exts.extend([".py"])

    files = list(_iter_files(root_dir, rel_roots=rel_roots, exts=exts, max_files=max_files))
    if not files:
        print("No indexable files found.")
        return False

    chunks: List[_Chunk] = []
    for rel in files:
        abs_path = os.path.join(root_dir, rel)
        try:
            if os.path.getsize(abs_path) > 300_000:
                continue
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            continue
        for ch in _chunk_text(rel, content, max_lines=60, max_chars=2000):
            chunks.append(ch)
            if len(chunks) >= max_chunks:
                break
        if len(chunks) >= max_chunks:
            break

    if dry_run:
        print(f"Index plan: files={len(files)} chunks={len(chunks)} allow_send_code={allow_send_code}")
        for rel in files[:20]:
            print(rel)
        if len(files) > 20:
            print("[TRUNCATED]")
        return True

    cfg = load_llm_config(root_path=root_dir)
    if cfg is None:
        print(
            "AI is disabled: set PROJMAN_LLM_API_KEY (or OPENAI_API_KEY). "
            "Optional: PROJMAN_LLM_BASE_URL / PROJMAN_LLM_EMBEDDING_MODEL."
        )
        return False

    inputs = [redact_secrets(ch.text)[: cfg.max_input_chars] for ch in chunks]
    try:
        vectors = openai_compatible_embeddings(cfg=cfg, inputs=inputs)
    except LLMError as exc:
        print(f"Error: {exc}")
        return False

    out_chunks = []
    for ch, vec in zip(chunks, vectors):
        out_chunks.append(
            {
                "path": ch.path,
                "start_line": ch.start_line,
                "end_line": ch.end_line,
                # Never persist raw secrets in the local index.
                "text": redact_secrets(ch.text)[:500],
                "embedding": vec,
            }
        )

    abs_index = _index_abs_path(root_dir)
    os.makedirs(os.path.dirname(abs_index), exist_ok=True)
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "root": ".",
        "embedding_model": cfg.embedding_model,
        "allow_send_code": allow_send_code,
        "files_indexed": len(files),
        "chunks_indexed": len(out_chunks),
        "chunks": out_chunks,
    }
    with open(abs_index, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    log.info("Semantic index written: %s chunks=%d", abs_index, len(out_chunks))
    print(os.path.relpath(abs_index, root_dir))
    return True


@register(
    "ai_search",
    needs_projects=False,
    needs_repositories=False,
    desc="Semantic search using embeddings index (requires API key).",
)
def ai_search(
    env: Dict[str, Any],
    projects_info: Dict[str, Any],
    query: str = "",
    top_k: int = 5,
    index_path: str = "",
) -> bool:
    """
    Query semantic search index built by `ai_index`.

    query (str): Natural language query.
    top_k (int): Number of results to print.
    index_path (str): Optional override path to index file (default: .cache/ai_index/semantic_index.json).
    """

    _ = projects_info

    query = str(query or "").strip()
    if not query:
        print("Error: query is required.")
        return False

    top_k = max(1, _to_int(top_k, default=5))

    root_dir = env.get("root_path") or os.getcwd()
    rel = _safe_relpath(index_path)
    if index_path and not rel:
        print("Error: index_path is invalid or unsafe.")
        return False
    abs_index = os.path.join(root_dir, rel) if rel else _index_abs_path(root_dir)
    if not os.path.isfile(abs_index):
        print(f"Error: index not found: {os.path.relpath(abs_index, root_dir)} (run ai_index first).")
        return False

    try:
        with open(abs_index, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"Error: failed to read index: {exc}")
        return False

    chunks = data.get("chunks") or []
    if not chunks:
        print("Error: index has no chunks.")
        return False

    cfg = load_llm_config(root_path=root_dir)
    if cfg is None:
        print(
            "AI is disabled: set PROJMAN_LLM_API_KEY (or OPENAI_API_KEY). "
            "Optional: PROJMAN_LLM_BASE_URL / PROJMAN_LLM_EMBEDDING_MODEL."
        )
        return False

    display_query = redact_secrets(query)
    try:
        q_vec = openai_compatible_embeddings(cfg=cfg, inputs=[display_query])[0]
    except LLMError as exc:
        print(f"Error: {exc}")
        return False

    scored = []
    for ch in chunks:
        vec = ch.get("embedding")
        if not isinstance(vec, list) or not vec:
            continue
        score = _cosine(q_vec, vec)
        scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)

    results = scored[:top_k]
    print(f"Semantic search: top_k={top_k} query={display_query!r}")
    for score, ch in results:
        path = ch.get("path") or ""
        start = ch.get("start_line") or 0
        end = ch.get("end_line") or 0
        snippet = redact_secrets(str(ch.get("text") or "")).replace("\n", " ").strip()
        if len(snippet) > 200:
            snippet = snippet[:200] + "..."
        print(f"- score={score:.3f} {path}:L{start}-L{end}")
        if snippet:
            print(f"  {snippet}")

    return True
