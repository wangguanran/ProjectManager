"""Lightweight OAuth helper for local login and token capture.

This module starts a temporary local HTTP server, generates a login URL with a
localhost redirect, captures the access token/code from the redirect, and stores
it to a token file and stdout so the caller can export it as an environment
variable.

Note: This is a generic helper intended for providers that support
`response_type=token` or `response_type=code` with a localhost redirect.
It does not perform token exchange; the captured value is treated as the
credential directly.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import socket
import sys
import threading
import time
import urllib.parse
from pathlib import Path


def _find_free_port() -> int:
    """Find an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class _TokenCaptureHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler to capture token via redirect."""

    token: str | None = None
    token_event: threading.Event | None = None
    token_path: Path | None = None

    def log_message(self, fmt: str, *args) -> None:  # pragma: no cover - quiet server
        return

    def _write(self, body: str, status: int = 200, content_type: str = "text/html") -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _store_token(self, token: str) -> None:
        self.__class__.token = token
        if self.__class__.token_path:
            self.__class__.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.__class__.token_path.write_text(token, encoding="utf-8")
        if self.__class__.token_event:
            self.__class__.token_event.set()

    def do_GET(self) -> None:  # noqa: N802 - http.server signature
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        # Direct query token (code or access_token)
        token = params.get("access_token", [None])[0] or params.get("token", [None])[0] or params.get("code", [None])[
            0
        ]

        if parsed.path == "/store" and token:
            self._store_token(token)
            self._write("<h3>登录成功，可关闭此页面。</h3>")
            return

        if parsed.path == "/callback":
            # Serve JS that reads fragment and posts to /store
            html = """
<!doctype html>
<html><body>
<h3>正在完成登录，请稍候…</h3>
<script>
  (function() {
    const hash = window.location.hash.startsWith('#') ? window.location.hash.substring(1) : '';
    const qs = new URLSearchParams(hash);
    const token = qs.get('access_token') || qs.get('token') || qs.get('code');
    if (token) {
      fetch('/store?token=' + encodeURIComponent(token))
        .then(() => document.body.innerHTML = '<h3>登录成功，可关闭此页面。</h3>')
        .catch(() => document.body.innerHTML = '<h3>保存失败，请重试。</h3>');
    } else {
      document.body.innerHTML = '<h3>未获取到 token，请重试。</h3>';
    }
  })();
</script>
</body></html>
"""
            self._write(html)
            return

        # Fallback root
        self._write("<h3>OAuth 回调已启动，请通过登录页完成授权。</h3>")


def run_login_flow(provider: str, env_name: str, timeout: int = 300) -> str | None:
    """Run the local login flow; return captured token or None."""
    token_dir = Path.home() / ".projectmanager_tokens"
    token_path = token_dir / f"{env_name}.txt"

    # Use cached token if present
    if token_path.exists():
        return token_path.read_text(encoding="utf-8").strip()

    port = _find_free_port()
    redirect_uri = f"http://localhost:{port}/callback"
    # Best-effort login URL; provider must allow localhost redirect. For OpenAI this
    # will only work if the client_id is registered; otherwise the user can still
    # paste the token/code into the URL fragment to complete capture.
    login_url = (
        "https://platform.openai.com/oauth/authorize"
        f"?client_id=projectmanager-cli"
        f"&redirect_uri={urllib.parse.quote(redirect_uri, safe='')}"
        "&response_type=token"
        "&scope=api.read+api.write"
    )

    event = threading.Event()
    _TokenCaptureHandler.token_event = event
    _TokenCaptureHandler.token_path = token_path

    server = http.server.HTTPServer(("localhost", port), _TokenCaptureHandler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print("请在浏览器打开以下登录地址完成授权：", file=sys.stderr)
    print(login_url, file=sys.stderr)
    print(f"授权后将重定向到 {redirect_uri} 自动保存 token。", file=sys.stderr)
    sys.stderr.flush()

    start = time.time()
    while time.time() - start < timeout:
        if event.wait(timeout=1):
            break

    # Shutdown server
    server.shutdown()
    thread.join(timeout=5)

    token = _TokenCaptureHandler.token
    if token:
        return token.strip()

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Local OAuth login helper")
    parser.add_argument("--provider", required=True, help="Provider name (e.g., openai)")
    parser.add_argument("--env-name", required=True, help="Env var to export the token to")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")
    args = parser.parse_args()

    token = run_login_flow(args.provider, args.env_name, timeout=args.timeout)
    if not token:
        print("", end="")  # stdout empty indicates failure
        return 1

    # Print token to stdout for caller to export
    print(token, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
