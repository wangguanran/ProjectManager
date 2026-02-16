from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def _initialize(server) -> None:
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }
    )
    assert resp is not None
    assert resp.get("result", {}).get("serverInfo", {}).get("name") == "projman-mcp"


def _tool_call(server, *, name: str, arguments: Dict[str, Any], msg_id: int = 2) -> Dict[str, Any]:
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    assert resp is not None
    return resp


def test_mcp_requires_initialize(tmp_path: Path) -> None:
    from src.plugins.mcp_server import MCPServer

    server = MCPServer(root_dir=str(tmp_path))
    resp = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert resp is not None
    assert resp["error"]["code"] == -32002


def test_mcp_tools_list_and_list_files_policy(tmp_path: Path) -> None:
    from src.plugins.mcp_server import MCPServer

    # Create a small repo-like tree with excluded entries.
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n", encoding="utf-8")

    server = MCPServer(root_dir=str(tmp_path))
    _initialize(server)

    resp = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert resp is not None
    tools: List[Dict[str, Any]] = resp["result"]["tools"]
    names = {t["name"] for t in tools}
    assert {"list_files", "read_file", "search_code", "get_repo_profile", "get_findings"}.issubset(names)

    call = _tool_call(server, name="list_files", arguments={"root": ".", "max_depth": 2, "limit": 100})
    result = call["result"]
    assert result.get("isError") is not True
    files = result["structuredContent"]["files"]
    assert "a.txt" in files
    assert ".env" not in files
    assert ".git/config" not in files


def test_mcp_read_file_policy_and_redaction(tmp_path: Path) -> None:
    from src.plugins.mcp_server import MCPServer

    (tmp_path / ".env").write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")
    token = "ghp_" + ("A" * 36)
    (tmp_path / "secrets.txt").write_text(f"{token}\nBearer xyz\n", encoding="utf-8")

    server = MCPServer(root_dir=str(tmp_path))
    _initialize(server)

    denied = _tool_call(server, name="read_file", arguments={"path": ".env"}, msg_id=10)["result"]
    assert denied.get("isError") is True

    traversal = _tool_call(server, name="read_file", arguments={"path": "../nope.txt"}, msg_id=11)["result"]
    assert traversal.get("isError") is True
    assert "unsafe" in traversal["content"][0]["text"]

    ok = _tool_call(server, name="read_file", arguments={"path": "secrets.txt"}, msg_id=12)["result"]
    text = ok["structuredContent"]["text"]
    assert token not in text
    assert "ghp_***" in text
    assert "Bearer ***" in text


def test_mcp_get_findings_missing_artifacts(tmp_path: Path) -> None:
    from src.plugins.mcp_server import MCPServer

    server = MCPServer(root_dir=str(tmp_path))
    _initialize(server)

    res = _tool_call(server, name="get_findings", arguments={}, msg_id=20)["result"]
    assert res.get("isError") is True
    assert "agent_artifacts" in res["content"][0]["text"]
