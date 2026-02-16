"""MCP stdio server (read-only by default).

This exposes a small set of safe, auditable tools for external AI agents.

Transport: newline-delimited JSON-RPC 2.0 over stdin/stdout.
IMPORTANT: stdout must be JSON-only.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.log_manager import log, redact_secrets
from src.operations.registry import register
from src.utils import get_version

_JSONRPC_VERSION = "2.0"

# Conservative defaults: exclude common large/sensitive dirs.
_EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    ".agent_artifacts",
    ".cache",
}

_EXCLUDE_FILES = {
    ".env",
    ".env.local",
    ".envrc",
}


def _json_dumps_one_line(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _safe_relpath(path: str) -> str:
    path = str(path or "").strip()
    if not path:
        return ""
    path = path.replace("\\", "/")
    # Reject absolute paths (POSIX) and Windows drive/UNC paths.
    if path.startswith("/"):
        return ""
    if re.match(r"^[A-Za-z]:/", path) or path.startswith("//"):
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


def _find_latest_run_dir(root_dir: str) -> Optional[str]:
    runs_dir = os.path.join(root_dir, ".agent_artifacts", "runs")
    if not os.path.isdir(runs_dir):
        return None
    candidates = [d for d in os.listdir(runs_dir) if os.path.isdir(os.path.join(runs_dir, d))]
    if not candidates:
        return None
    # run_id is timestamp-prefixed; lexical sort matches time order.
    candidates.sort()
    return os.path.join(runs_dir, candidates[-1])


def _read_run_json(root_dir: str, *, name: str) -> Tuple[Optional[Dict[str, Any]], str]:
    run_dir = _find_latest_run_dir(root_dir)
    if not run_dir:
        return None, "No .agent_artifacts runs found"
    index_path = os.path.join(run_dir, "index.json")
    if not os.path.exists(index_path):
        return None, "Run index.json not found"
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    except (OSError, ValueError) as exc:
        return None, f"Failed to read index.json: {exc}"

    rel = (index.get("files") or {}).get(name)
    if not rel:
        return None, f"index.json missing files.{name}"
    target = os.path.join(run_dir, rel)
    if not os.path.exists(target):
        return None, f"Missing artifact: {rel}"
    try:
        with open(target, "r", encoding="utf-8") as f:
            return json.load(f), ""
    except (OSError, ValueError) as exc:
        return None, f"Failed to read {rel}: {exc}"


def _tool_ok_text(text: str, *, structured: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {"content": [{"type": "text", "text": text}]}
    if structured is not None:
        result["structuredContent"] = structured
    return result


def _tool_error(text: str) -> Dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": True}


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPServer:
    def __init__(self, *, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self._initialized = False
        self._shutdown = False

        self._tools: Dict[str, ToolDef] = {
            "list_files": ToolDef(
                name="list_files",
                description="List repository files (safe relpaths; excludes .git/.env/.agent_artifacts/.cache).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "root": {"type": "string", "description": "Relative root to list (default '.')"},
                        "max_depth": {"type": "integer", "minimum": 0, "default": 4},
                        "limit": {"type": "integer", "minimum": 1, "default": 500},
                        "include_hidden": {"type": "boolean", "default": False},
                    },
                },
            ),
            "read_file": ToolDef(
                name="read_file",
                description="Read a text file by relative path (denies .env/.git/.agent_artifacts/.cache).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "max_bytes": {"type": "integer", "minimum": 1, "default": 200_000},
                        "redact": {"type": "boolean", "default": True},
                    },
                    "required": ["path"],
                },
            ),
            "search_code": ToolDef(
                name="search_code",
                description="Search code using ripgrep (fixed-string by default).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "glob": {"type": "string", "description": "Optional rg --glob pattern (e.g. '*.py')"},
                        "limit": {"type": "integer", "minimum": 1, "default": 100},
                        "regex": {"type": "boolean", "default": False},
                        "redact": {"type": "boolean", "default": True},
                    },
                    "required": ["query"],
                },
            ),
            "get_repo_profile": ToolDef(
                name="get_repo_profile",
                description="Read latest repo_profile.json from .agent_artifacts (if present).",
                input_schema={"type": "object", "properties": {}},
            ),
            "get_findings": ToolDef(
                name="get_findings",
                description="Read latest findings.json from .agent_artifacts (if present).",
                input_schema={"type": "object", "properties": {}},
            ),
        }

    def should_exit(self) -> bool:
        return bool(self._shutdown)

    def handle(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(msg, dict):
            return None

        method = msg.get("method")
        msg_id = msg.get("id", None)
        params = msg.get("params") or {}

        # Notifications have no id; never respond.
        is_notification = "id" not in msg

        if method == "initialize":
            self._initialized = True
            client_ver = (params.get("protocolVersion") or "draft").strip()
            result = {
                "protocolVersion": client_ver,
                "capabilities": {
                    "tools": {},
                    "resources": {"subscribe": False, "listChanged": False},
                },
                "serverInfo": {
                    "name": "projman-mcp",
                    "version": get_version(),
                },
                "instructions": (
                    "ProjectManager MCP server (read-only). "
                    "Tools are path-sandboxed and exclude .git/.env/.agent_artifacts/.cache by default."
                ),
            }
            return {"jsonrpc": _JSONRPC_VERSION, "id": msg_id, "result": result}

        if method == "notifications/initialized":
            return None

        if method == "shutdown":
            self._shutdown = True
            return {"jsonrpc": _JSONRPC_VERSION, "id": msg_id, "result": None}

        if method == "exit":
            # Notification (no response); server loop should exit when seeing _shutdown.
            self._shutdown = True
            return None

        if not self._initialized and method not in {"initialize"}:
            # Protocol-level: must initialize first.
            if is_notification:
                return None
            return self._err(msg_id, code=-32002, message="Server not initialized")

        if method == "tools/list":
            tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.input_schema,
                }
                for t in self._tools.values()
            ]
            return {"jsonrpc": _JSONRPC_VERSION, "id": msg_id, "result": {"tools": tools}}

        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not isinstance(name, str) or not name:
                return {"jsonrpc": _JSONRPC_VERSION, "id": msg_id, "result": _tool_error("Missing tool name")}
            if name not in self._tools:
                return self._err(msg_id, code=-32601, message=f"Unknown tool: {name}")
            try:
                result = self._call_tool(name, arguments)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                # Tool execution error: return isError so model can self-correct.
                safe = redact_secrets(str(exc))[:800]
                result = _tool_error(f"Tool execution failed: {safe}")
            return {"jsonrpc": _JSONRPC_VERSION, "id": msg_id, "result": result}

        if method == "resources/list":
            # MVP: no explicit resources; use tools instead.
            return {"jsonrpc": _JSONRPC_VERSION, "id": msg_id, "result": {"resources": []}}

        if method == "resources/read":
            return {"jsonrpc": _JSONRPC_VERSION, "id": msg_id, "result": _tool_error("resources/read not supported")}

        if is_notification:
            return None
        return self._err(msg_id, code=-32601, message=f"Method not found: {method}")

    def _err(self, msg_id: Any, *, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": _JSONRPC_VERSION, "id": msg_id, "error": {"code": int(code), "message": message}}

    def _call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name == "list_files":
            return self._tool_list_files(arguments)
        if name == "read_file":
            return self._tool_read_file(arguments)
        if name == "search_code":
            return self._tool_search_code(arguments)
        if name == "get_repo_profile":
            return self._tool_get_artifact(arguments, artifact_name="repo_profile")
        if name == "get_findings":
            return self._tool_get_artifact(arguments, artifact_name="findings")
        raise RuntimeError(f"Unhandled tool: {name}")

    def _tool_list_files(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        raw_root = arguments.get("root", ".")
        root = _safe_relpath(raw_root)
        if str(raw_root or "").strip() not in {"", ".", "./"} and not root:
            return _tool_error("root is invalid or unsafe")
        max_depth = int(arguments.get("max_depth", 4))
        limit = int(arguments.get("limit", 500))
        include_hidden = bool(arguments.get("include_hidden", False))

        base = self.root_dir if not root else os.path.join(self.root_dir, root)
        if not os.path.isdir(base):
            return _tool_error("root is not a directory")

        out: List[str] = []
        base_depth = base.rstrip(os.sep).count(os.sep)
        for dirpath, dirnames, filenames in os.walk(base):
            rel_dir = os.path.relpath(dirpath, self.root_dir).replace("\\", "/")
            rel_dir = "" if rel_dir == "." else rel_dir

            # prune excluded dirs
            keep: List[str] = []
            for d in dirnames:
                rel = f"{rel_dir}/{d}" if rel_dir else d
                if not include_hidden and d.startswith("."):
                    continue
                if _is_excluded(rel):
                    continue
                keep.append(d)
            dirnames[:] = keep

            cur_depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
            if cur_depth > max_depth:
                dirnames[:] = []
                continue

            for fn in sorted(filenames):
                if not include_hidden and fn.startswith("."):
                    continue
                rel = f"{rel_dir}/{fn}" if rel_dir else fn
                rel = rel.replace("\\", "/")
                if _is_excluded(rel):
                    continue
                out.append(rel)
                if len(out) >= limit:
                    break
            if len(out) >= limit:
                break

        structured = {"root": root or ".", "files": out, "truncated": len(out) >= limit}
        return _tool_ok_text(_json_dumps_one_line(structured), structured=structured)

    def _tool_read_file(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        raw_path = arguments.get("path", "")
        rel = _safe_relpath(raw_path)
        if not rel:
            if str(raw_path or "").strip():
                return _tool_error("path is invalid or unsafe")
            return _tool_error("path is required")
        if _is_excluded(rel):
            return _tool_error("path is excluded by policy")
        max_bytes = int(arguments.get("max_bytes", 200_000))
        redact = bool(arguments.get("redact", True))

        abs_path = os.path.join(self.root_dir, rel)
        abs_path = os.path.abspath(abs_path)
        if not abs_path.startswith(self.root_dir + os.sep) and abs_path != self.root_dir:
            return _tool_error("unsafe path (escape attempt)")
        if not os.path.isfile(abs_path):
            return _tool_error("path is not a file")

        try:
            with open(abs_path, "rb") as f:
                data = f.read(max_bytes + 1)
        except OSError as exc:
            return _tool_error(f"read failed: {exc}")

        truncated = len(data) > max_bytes
        if truncated:
            data = data[:max_bytes]
        text = data.decode("utf-8", errors="replace")
        if truncated:
            text += "\n[TRUNCATED]\n"

        if redact:
            text = redact_secrets(text)

        structured = {"path": rel, "truncated": truncated, "text": text}
        return _tool_ok_text(text, structured=structured)

    def _tool_search_code(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        query = str(arguments.get("query", "") or "").strip()
        if not query:
            return _tool_error("query is required")
        if len(query) > 200:
            return _tool_error("query too long")

        limit = int(arguments.get("limit", 100))
        regex = bool(arguments.get("regex", False))
        glob = str(arguments.get("glob", "") or "").strip()
        redact = bool(arguments.get("redact", True))

        cmd = ["rg", "-n", "--no-messages"]
        if not regex:
            cmd.append("-F")
        if glob:
            cmd.extend(["--glob", glob])
        # Exclude large/sensitive dirs
        for d in sorted(_EXCLUDE_DIRS):
            cmd.extend(["--glob", f"!{d}/**"])
        cmd.append(query)
        cmd.append(".")

        try:
            cp = subprocess.run(cmd, cwd=self.root_dir, capture_output=True, text=True, check=False)
            backend = "rg"
            raw_lines = (cp.stdout or "").splitlines()
        except OSError:
            cp = None
            backend = "python"
            raw_lines = self._python_search(
                query=query,
                glob=glob,
                limit=limit,
                regex=regex,
                max_bytes_per_file=200_000,
            )

        lines: List[str] = []
        for raw in raw_lines:
            line = str(raw).strip()
            if not line:
                continue
            if redact:
                line = redact_secrets(line)
            lines.append(line)
            if len(lines) >= limit:
                break

        structured = {
            "query": query,
            "glob": glob,
            "regex": regex,
            "backend": backend,
            "matches": lines,
            "truncated": len(lines) >= limit,
            "rc": getattr(cp, "returncode", None),
        }
        return _tool_ok_text(_json_dumps_one_line(structured), structured=structured)

    def _tool_get_artifact(self, _arguments: Dict[str, Any], *, artifact_name: str) -> Dict[str, Any]:
        data, err = _read_run_json(self.root_dir, name=artifact_name)
        if data is None:
            return _tool_error(err)
        text = _json_dumps_one_line(data)
        return _tool_ok_text(text, structured=data)

    def _python_search(
        self,
        *,
        query: str,
        glob: str,
        limit: int,
        regex: bool,
        max_bytes_per_file: int,
    ) -> List[str]:
        """Fallback search when rg is unavailable.

        Produces "relpath:line:text" lines similar to ripgrep (best-effort).
        """
        matcher = None
        if regex:
            try:
                matcher = re.compile(query)
            except re.error:
                return []

        out: List[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            rel_dir = os.path.relpath(dirpath, self.root_dir).replace("\\", "/")
            rel_dir = "" if rel_dir == "." else rel_dir

            keep: List[str] = []
            for d in dirnames:
                rel = f"{rel_dir}/{d}" if rel_dir else d
                if d.startswith("."):
                    continue
                if _is_excluded(rel):
                    continue
                keep.append(d)
            dirnames[:] = keep

            for fn in sorted(filenames):
                if fn.startswith("."):
                    continue
                rel = f"{rel_dir}/{fn}" if rel_dir else fn
                rel = rel.replace("\\", "/")
                if _is_excluded(rel):
                    continue
                if glob and not (fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(fn, glob)):
                    continue
                abs_path = os.path.join(self.root_dir, rel)
                try:
                    if os.path.getsize(abs_path) > max_bytes_per_file:
                        continue
                except OSError:
                    continue

                try:
                    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                        for idx, line in enumerate(f, start=1):
                            hay = line.rstrip("\n")
                            ok = bool(matcher.search(hay)) if matcher is not None else (query in hay)
                            if not ok:
                                continue
                            text = hay.rstrip()
                            if len(text) > 400:
                                text = text[:400] + "..."
                            out.append(f"{rel}:{idx}:{text}")
                            if len(out) >= limit:
                                return out
                except OSError:
                    continue

        return out


@register(
    "mcp_server",
    needs_projects=False,
    needs_repositories=False,
    desc="Start MCP stdio server (read-only tools; stdout is JSON-only).",
)
def mcp_server(env: Dict[str, Any], projects_info: Dict[str, Any], root: str = ".") -> bool:
    """
    Start an MCP server over stdio (newline-delimited JSON-RPC).

    root (str): Root directory for path sandboxing (default: current working directory).
    """

    _ = projects_info
    root_path = env.get("root_path") or os.getcwd()
    root_dir = root
    if not os.path.isabs(root_dir):
        root_dir = os.path.join(root_path, root_dir)
    root_dir = os.path.abspath(root_dir)

    server = MCPServer(root_dir=root_dir)

    # IMPORTANT: do not print anything to stdout other than JSON-RPC messages.
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            # Parse error: best-effort, no id available.
            err = {"jsonrpc": _JSONRPC_VERSION, "id": None, "error": {"code": -32700, "message": "Parse error"}}
            sys.stdout.write(_json_dumps_one_line(err) + "\n")
            sys.stdout.flush()
            continue

        resp = server.handle(msg)
        if resp is None:
            if server.should_exit() and (msg.get("method") == "exit"):
                break
            continue
        sys.stdout.write(_json_dumps_one_line(resp) + "\n")
        sys.stdout.flush()

    log.info("MCP server stdin closed; exiting.")
    return True
