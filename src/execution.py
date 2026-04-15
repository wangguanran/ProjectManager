"""Shared execution session, render-mode selection, and raw-output rendering."""

# pylint: disable=missing-function-docstring,too-many-instance-attributes

from __future__ import annotations

import json
import sys
import threading
import time
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

SUPPORTED_EXECUTION_UI_OPERATIONS = {
    "board_del",
    "board_new",
    "doctor",
    "project_build",
    "project_del",
    "project_diff",
    "project_new",
    "project_pre_build",
    "project_do_build",
    "project_post_build",
    "po_apply",
    "po_analyze",
    "po_clear",
    "po_del",
    "po_list",
    "po_new",
    "po_revert",
    "po_status",
    "po_update",
    "update",
    "upgrade",
}
DIRECT_OUTPUT_FLAGS = {"json", "emit_plan"}
RAW_OUTPUT_FALLBACK_OPERATIONS = {"po_del"}
_CURRENT_STEP_ID: ContextVar[Optional[str]] = ContextVar("projman_current_step_id", default=None)


def _truthy(value: Any) -> bool:
    if value in (None, False):
        return False
    if value is True:
        return True
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def is_interactive_tty() -> bool:
    """Return True when stdin/stdout are interactive TTYs."""
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (AttributeError, OSError, ValueError):  # pragma: no cover
        return False


def resolve_render_mode(operate: str, args_dict: Dict[str, Any], parsed_kwargs: Dict[str, Any]) -> str:
    """Choose `interactive_tui`, `raw_output`, or `direct_output` for this run."""
    if _truthy(args_dict.get("raw_output")):
        return "raw_output"

    if any(_truthy(parsed_kwargs.get(flag)) for flag in DIRECT_OUTPUT_FLAGS):
        return "direct_output"

    if operate not in SUPPORTED_EXECUTION_UI_OPERATIONS:
        return "direct_output"

    if not is_interactive_tty():
        return "raw_output"

    if operate in RAW_OUTPUT_FALLBACK_OPERATIONS and not _truthy(parsed_kwargs.get("force")):
        return "raw_output"

    return "interactive_tui"


def describe_operation(operate: str, name: Optional[str]) -> str:
    """Human-readable operation title for session roots."""
    base = operate.replace("_", " ").strip()
    if name:
        return f"{base}: {name}"
    return base


def _format_command(command: Any) -> str:
    if isinstance(command, list):
        return " ".join(f'"{arg}"' if " " in str(arg) else str(arg) for arg in command)
    return str(command)


def make_step_id(*parts: Any) -> str:
    """Create a stable, display-safe step id."""
    items = [str(part).strip() for part in parts if str(part).strip()]
    safe = []
    for item in items:
        safe.append("".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in item))
    return ".".join(safe)


@dataclass
class StepRecord:
    """In-memory state for one execution step."""

    step_id: str
    title: str
    parent_id: Optional[str]
    state: str = "pending"
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    elapsed_s: float = 0.0
    summary: str = ""
    logs: List[Dict[str, str]] = field(default_factory=list)
    command: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExecutionRenderer:
    """Simple renderer protocol."""

    def on_event(self, event: Dict[str, Any]) -> None:  # pragma: no cover - interface only
        raise NotImplementedError


class RawOutputRenderer(ExecutionRenderer):
    """Machine-safe line-oriented stdout renderer."""

    def __init__(self, stream=None) -> None:
        self.stream = stream or sys.stdout
        self._lock = threading.Lock()

    @staticmethod
    def _quote(value: Any) -> str:
        return json.dumps("" if value is None else str(value), ensure_ascii=False)

    def _write(self, line: str) -> None:
        with self._lock:
            print(line, file=self.stream, flush=True)

    def on_event(self, event: Dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "step_started":
            parts = [
                "STEP_START",
                f"id={event['step_id']}",
                f"title={self._quote(event.get('title', ''))}",
            ]
            if event.get("parent_id"):
                parts.append(f"parent={event['parent_id']}")
            self._write(" ".join(parts))
            return

        if event_type == "step_log":
            text = str(event.get("text") or "")
            lines = text.splitlines() or ([text] if text else [])
            for line in lines:
                self._write(
                    " ".join(
                        [
                            "LOG",
                            f"id={event['step_id']}",
                            f"stream={event.get('stream', 'stdout')}",
                            f"text={self._quote(line)}",
                        ]
                    )
                )
            return

        if event_type == "step_command_started":
            self._write(
                " ".join(
                    [
                        "COMMAND_START",
                        f"id={event['step_id']}",
                        f"desc={self._quote(event.get('description', ''))}",
                        f"cwd={self._quote(event.get('cwd', ''))}",
                        f"cmd={self._quote(event.get('command', ''))}",
                    ]
                )
            )
            return

        if event_type == "step_command_finished":
            parts = [
                "COMMAND_END",
                f"id={event['step_id']}",
                f"rc={int(event.get('returncode', 0))}",
            ]
            if event.get("description"):
                parts.append(f"desc={self._quote(event['description'])}")
            self._write(" ".join(parts))
            return

        if event_type == "step_finished":
            parts = [
                "STEP_END",
                f"id={event['step_id']}",
                f"state={event.get('state', 'success')}",
                f"duration={event.get('duration', 0.0):.2f}s",
            ]
            if event.get("exit_code") is not None:
                parts.append(f"rc={int(event['exit_code'])}")
            if event.get("summary"):
                parts.append(f"summary={self._quote(event['summary'])}")
            self._write(" ".join(parts))
            return

        if event_type == "session_summary":
            self._write(
                " ".join(
                    [
                        "SESSION_END",
                        f"state={event.get('state', 'success')}",
                        f"duration={event.get('duration', 0.0):.2f}s",
                        f"title={self._quote(event.get('title', ''))}",
                    ]
                )
            )


class _ExecutionLogStream:
    """Redirect `print()` output into the active execution step log."""

    def __init__(self, session: "ExecutionSession", stream_name: str) -> None:
        self._session = session
        self._stream_name = stream_name
        self._buffer = ""
        self._lock = threading.Lock()

    def write(self, text: Any) -> int:
        value = "" if text is None else str(text)
        if not value:
            return 0

        with self._lock:
            self._buffer += value
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line:
                    self._session.log(line, stream=self._stream_name)
        return len(value)

    def flush(self) -> None:
        with self._lock:
            if self._buffer:
                self._session.log(self._buffer, stream=self._stream_name)
                self._buffer = ""

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True


class ExecutionSession:
    """Thread-safe event session shared by commands and renderers."""

    def __init__(self, *, title: str, mode: str) -> None:
        self.title = title
        self.mode = mode
        self.started_at = time.monotonic()
        self.started_at_iso = datetime.now().isoformat()
        self._lock = threading.RLock()
        self._steps: Dict[str, StepRecord] = {}
        self._renderers: List[ExecutionRenderer] = []

    def add_renderer(self, renderer: ExecutionRenderer) -> None:
        with self._lock:
            if renderer not in self._renderers:
                self._renderers.append(renderer)

    def remove_renderer(self, renderer: ExecutionRenderer) -> None:
        with self._lock:
            self._renderers = [item for item in self._renderers if item is not renderer]

    def snapshot_steps(self) -> Dict[str, StepRecord]:
        with self._lock:
            return dict(self._steps)

    def _emit(self, event: Dict[str, Any]) -> None:
        with self._lock:
            renderers = list(self._renderers)
        for renderer in renderers:
            renderer.on_event(event)

    @property
    def current_step_id(self) -> Optional[str]:
        return _CURRENT_STEP_ID.get()

    @contextmanager
    def bind_step(self, step_id: str) -> Iterator[str]:
        token = _CURRENT_STEP_ID.set(step_id)
        try:
            yield step_id
        finally:
            _CURRENT_STEP_ID.reset(token)

    def start_step(
        self,
        step_id: str,
        title: str,
        *,
        parent_id: Optional[str] = None,
        summary: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if parent_id is None:
            parent_id = self.current_step_id

        with self._lock:
            record = self._steps.get(step_id)
            if record is None:
                record = StepRecord(
                    step_id=step_id,
                    title=title,
                    parent_id=parent_id,
                    state="running",
                    started_at=time.monotonic(),
                    summary=summary,
                    metadata=dict(metadata or {}),
                )
                self._steps[step_id] = record
            else:
                record.title = title
                record.parent_id = parent_id
                record.state = "running"
                record.started_at = time.monotonic()
                record.summary = summary
                if metadata:
                    record.metadata.update(metadata)

        self._emit(
            {
                "type": "step_started",
                "step_id": step_id,
                "title": title,
                "parent_id": parent_id,
                "summary": summary,
                "started_at": datetime.now().isoformat(),
            }
        )
        return step_id

    def finish_step(
        self,
        step_id: str,
        *,
        state: str,
        summary: str = "",
        exit_code: Optional[int] = None,
    ) -> None:
        with self._lock:
            record = self._steps.get(step_id)
            if record is None:
                return
            record.state = state
            record.ended_at = time.monotonic()
            if record.started_at is not None:
                record.elapsed_s = max(0.0, record.ended_at - record.started_at)
            if summary:
                record.summary = summary
            if exit_code is not None:
                record.command["exit_code"] = int(exit_code)

        self._emit(
            {
                "type": "step_finished",
                "step_id": step_id,
                "state": state,
                "duration": record.elapsed_s,
                "summary": record.summary,
                "exit_code": exit_code,
                "finished_at": datetime.now().isoformat(),
            }
        )

    @contextmanager
    def step(
        self,
        step_id: str,
        title: str,
        *,
        parent_id: Optional[str] = None,
        summary: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[str]:
        self.start_step(step_id, title, parent_id=parent_id, summary=summary, metadata=metadata)
        with self.bind_step(step_id):
            try:
                yield step_id
            except Exception as exc:
                self.finish_step(step_id, state="failed", summary=str(exc))
                raise
            self.finish_step(step_id, state="success", summary=summary)

    def log(self, text: Any, *, stream: str = "stdout", step_id: Optional[str] = None) -> None:
        message = "" if text is None else str(text)
        if not message:
            return

        target_step = step_id or self.current_step_id
        if not target_step:
            return

        with self._lock:
            record = self._steps.get(target_step)
            if record is not None:
                record.logs.append({"stream": stream, "text": message})

        self._emit(
            {
                "type": "step_log",
                "step_id": target_step,
                "stream": stream,
                "text": message,
            }
        )

    def command_started(
        self,
        *,
        command: Any,
        cwd: Optional[str],
        description: str,
        step_id: Optional[str] = None,
    ) -> None:
        target_step = step_id or self.current_step_id
        if not target_step:
            return

        payload = {
            "command": _format_command(command),
            "cwd": cwd or "",
            "description": description or "",
            "started_at": datetime.now().isoformat(),
        }
        with self._lock:
            record = self._steps.get(target_step)
            if record is not None:
                record.command.update(payload)

        self._emit({"type": "step_command_started", "step_id": target_step, **payload})

    def command_finished(
        self,
        *,
        command: Any,
        cwd: Optional[str],
        description: str,
        returncode: int,
        stdout: str,
        stderr: str,
        step_id: Optional[str] = None,
    ) -> None:
        target_step = step_id or self.current_step_id
        if not target_step:
            return

        payload = {
            "command": _format_command(command),
            "cwd": cwd or "",
            "description": description or "",
            "returncode": int(returncode),
            "finished_at": datetime.now().isoformat(),
        }
        with self._lock:
            record = self._steps.get(target_step)
            if record is not None:
                record.command.update(payload)

        self._emit({"type": "step_command_finished", "step_id": target_step, **payload})
        self.log(stdout, stream="stdout", step_id=target_step)
        self.log(stderr, stream="stderr", step_id=target_step)

    def emit_summary(self, *, state: str) -> None:
        self._emit(
            {
                "type": "session_summary",
                "title": self.title,
                "state": state,
                "duration": max(0.0, time.monotonic() - self.started_at),
                "started_at": self.started_at_iso,
                "finished_at": datetime.now().isoformat(),
            }
        )


def get_execution_session(env: Dict[str, Any]) -> Optional[ExecutionSession]:
    """Return the current execution session from env, if one is active."""
    if not isinstance(env, dict):
        return None
    session = env.get("execution_session")
    return session if isinstance(session, ExecutionSession) else None


@contextmanager
def execution_step(
    env: Dict[str, Any],
    step_id: str,
    title: str,
    *,
    parent_id: Optional[str] = None,
    summary: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Iterator[Optional[str]]:
    """Context manager that becomes a no-op when no execution session is active."""
    session = get_execution_session(env)
    if session is None:
        yield None
        return

    with session.step(step_id, title, parent_id=parent_id, summary=summary, metadata=metadata) as active_step:
        yield active_step


def execution_log(env: Dict[str, Any], text: Any, *, stream: str = "stdout") -> None:
    """Append log text to the active execution step when a session exists."""
    session = get_execution_session(env)
    if session is not None:
        session.log(text, stream=stream)


def execute_operation_with_session(session: ExecutionSession, operate: str, operation) -> Any:
    """Run one operation under the session root step and emit the final summary."""
    root_step_id = make_step_id("operation", operate)
    session.start_step(root_step_id, session.title)
    stdout_stream = _ExecutionLogStream(session, "stdout")
    stderr_stream = _ExecutionLogStream(session, "stderr")

    try:
        with session.bind_step(root_step_id):
            with redirect_stdout(stdout_stream):
                with redirect_stderr(stderr_stream):
                    result = operation()
    except Exception as exc:
        stdout_stream.flush()
        stderr_stream.flush()
        session.log(str(exc), stream="stderr", step_id=root_step_id)
        session.finish_step(root_step_id, state="failed", summary=str(exc))
        session.emit_summary(state="failed")
        raise

    stdout_stream.flush()
    stderr_stream.flush()
    if result is False:
        session.finish_step(root_step_id, state="failed", summary="Operation returned failure status.")
        session.emit_summary(state="failed")
        return result

    session.finish_step(root_step_id, state="success", summary="Completed.")
    session.emit_summary(state="success")
    return result
