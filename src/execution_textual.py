"""Textual renderer for interactive execution sessions."""

# mypy: disable-error-code=import-not-found
# pylint: disable=missing-function-docstring,missing-class-docstring,too-many-instance-attributes,broad-exception-caught

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from src.execution import ExecutionRenderer, ExecutionSession, RawOutputRenderer


class TextualUnavailable(RuntimeError):
    """Raised when the interactive Textual renderer cannot be started."""


def run_textual_session(session: ExecutionSession, operation) -> Any:
    """Run one operation inside the Textual execution UI."""
    try:
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.containers import Horizontal, Vertical
        from textual.widgets import Footer, Header, RichLog, Static, Tree
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised only when dependency is missing
        raise TextualUnavailable("Textual is not installed. Re-run with --raw-output or install the package.") from exc

    class _TextualSessionRenderer(ExecutionRenderer):
        def __init__(self, app: "ExecutionTextualApp") -> None:
            self.app = app

        def on_event(self, event: Dict[str, Any]) -> None:
            self.app.call_from_thread(self.app.apply_session_event, event)

    class ExecutionTextualApp(App[bool]):
        CSS = """
        Screen {
            layout: vertical;
        }

        #body {
            height: 1fr;
        }

        #steps-pane {
            width: 36%;
            min-width: 36;
            border: solid $panel;
        }

        #right-pane {
            width: 64%;
        }

        #logs {
            height: 1fr;
            border: solid $panel;
        }

        #details {
            height: 10;
            border: solid $panel;
            padding: 0 1;
        }
        """

        BINDINGS = [
            Binding("q", "detach", "Detach"),
            Binding("f", "focus_active", "Follow active"),
            Binding("a", "toggle_auto_follow", "Auto-follow"),
            Binding("enter", "toggle_selected", "Expand/collapse"),
            Binding("space", "toggle_selected", "Expand/collapse"),
        ]

        def __init__(self, run_operation) -> None:
            super().__init__()
            self._run_operation = run_operation
            self._renderer = _TextualSessionRenderer(self)
            self._worker: Optional[threading.Thread] = None
            self._result: Any = None
            self._error: Optional[BaseException] = None
            self.detached = False
            self.auto_follow = True
            self.active_step_id: Optional[str] = None
            self.selected_step_id: Optional[str] = None
            self.failed_step_id: Optional[str] = None
            self._nodes: Dict[str, Any] = {}
            self._step_state: Dict[str, Dict[str, Any]] = {}

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal(id="body"):
                yield Tree("Execution", id="steps-pane")
                with Vertical(id="right-pane"):
                    yield RichLog(id="logs", highlight=True, markup=False)
                    yield Static("Waiting for execution to start…", id="details")
            yield Footer()

        def on_mount(self) -> None:
            self.title = session.title
            self.sub_title = "Auto-follow on"

            self.steps = self.query_one("#steps-pane", Tree)
            self.logs = self.query_one("#logs", RichLog)
            self.details = self.query_one("#details", Static)
            self.steps.root.expand()
            self.steps.focus()

            session.add_renderer(self._renderer)
            self._worker = threading.Thread(target=self._run_in_worker, daemon=False)
            self._worker.start()

        def on_unmount(self) -> None:
            session.remove_renderer(self._renderer)

        @property
        def result(self) -> Any:
            return self._result

        @property
        def error(self) -> Optional[BaseException]:
            return self._error

        def worker_is_alive(self) -> bool:
            return bool(self._worker and self._worker.is_alive())

        def join_worker(self) -> None:
            if self._worker is not None:
                self._worker.join()

        def _run_in_worker(self) -> None:
            try:
                self._result = self._run_operation()
            except Exception as exc:  # pragma: no cover - the UI only relays the error
                self._error = exc
            finally:
                self.call_from_thread(self._handle_operation_finished)

        def _handle_operation_finished(self) -> None:
            if self._error is not None or self._result is False:
                if self.failed_step_id:
                    self._select_step(self.failed_step_id)
                self.sub_title = "Execution failed; inspect logs and press q to detach"
                return
            self.exit(True)

        def apply_session_event(self, event: Dict[str, Any]) -> None:
            event_type = event.get("type")
            if event_type == "step_started":
                self._on_step_started(event)
                return
            if event_type == "step_log":
                self._on_step_log(event)
                return
            if event_type == "step_command_started":
                self._on_command_started(event)
                return
            if event_type == "step_command_finished":
                self._on_command_finished(event)
                return
            if event_type == "step_finished":
                self._on_step_finished(event)
                return
            if event_type == "session_summary":
                self._on_session_summary(event)

        def _node_label(self, step_id: str) -> str:
            info = self._step_state[step_id]
            state_icon = {
                "pending": "…",
                "running": "▶",
                "success": "✓",
                "failed": "✗",
                "skipped": "○",
            }.get(info.get("state", "pending"), "•")
            duration = info.get("duration")
            duration_text = f" [{duration:.2f}s]" if isinstance(duration, (int, float)) and duration > 0 else ""
            summary = info.get("summary") or ""
            suffix = f" - {summary}" if summary else ""
            return f"{state_icon} {info.get('title', step_id)}{duration_text}{suffix}"

        def _refresh_log_and_details(self) -> None:
            target_id = self.selected_step_id or self.active_step_id
            if not target_id or target_id not in self._step_state:
                return

            info = self._step_state[target_id]
            self.logs.clear()
            for item in info.get("logs", []):
                prefix = "stderr" if item.get("stream") == "stderr" else "stdout"
                text = str(item.get("text") or "")
                for line in text.splitlines() or ([text] if text else []):
                    self.logs.write(f"[{prefix}] {line}")

            command = info.get("command") or {}
            detail_lines = [
                f"Step: {info.get('title', target_id)}",
                f"State: {info.get('state', 'pending')}",
                f"Started: {info.get('started_at', '-')}",
                f"Finished: {info.get('finished_at', '-')}",
                f"Elapsed: {info.get('duration', 0.0):.2f}s",
                f"Summary: {info.get('summary', '') or '-'}",
                f"Command: {command.get('command', '-')}",
                f"Cwd: {command.get('cwd', '-')}",
                f"Exit code: {command.get('returncode', '-')}",
            ]
            self.details.update("\n".join(detail_lines))

        def _select_step(self, step_id: str) -> None:
            self.selected_step_id = step_id
            node = self._nodes.get(step_id)
            if node is not None:
                if hasattr(self.steps, "select_node"):
                    self.steps.select_node(node)
                if hasattr(self.steps, "move_cursor"):
                    self.steps.move_cursor(node)
            self._refresh_log_and_details()

        def _on_step_started(self, event: Dict[str, Any]) -> None:
            step_id = event["step_id"]
            parent_id = event.get("parent_id")
            parent_node = self.steps.root if parent_id is None else self._nodes.get(str(parent_id), self.steps.root)
            node = parent_node.add(self._node_label_for_event(event), data=step_id, expand=False)
            if parent_id is None:
                node.expand()

            self._nodes[step_id] = node
            self._step_state[step_id] = {
                "title": event.get("title", step_id),
                "state": "running",
                "summary": event.get("summary", ""),
                "started_at": event.get("started_at", session.started_at_iso),
                "finished_at": "-",
                "duration": 0.0,
                "logs": [],
                "command": {},
            }
            self.active_step_id = step_id
            if self.auto_follow or self.selected_step_id is None:
                self._select_step(step_id)

        def _node_label_for_event(self, event: Dict[str, Any]) -> str:
            return f"▶ {event.get('title', event['step_id'])}"

        def _on_step_log(self, event: Dict[str, Any]) -> None:
            info = self._step_state.get(event["step_id"])
            if info is None:
                return
            info.setdefault("logs", []).append({"stream": event.get("stream", "stdout"), "text": event.get("text", "")})
            if self.auto_follow and event["step_id"] == self.active_step_id:
                self.selected_step_id = event["step_id"]
            if self.selected_step_id == event["step_id"]:
                self._refresh_log_and_details()

        def _on_command_started(self, event: Dict[str, Any]) -> None:
            info = self._step_state.get(event["step_id"])
            if info is None:
                return
            info["command"] = {
                "command": event.get("command", ""),
                "cwd": event.get("cwd", ""),
                "description": event.get("description", ""),
                "returncode": "-",
            }
            info.setdefault("logs", []).append(
                {
                    "stream": "stdout",
                    "text": f"$ {event.get('command', '')} (cwd={event.get('cwd', '') or '.'})",
                }
            )
            if self.selected_step_id == event["step_id"] or (
                self.auto_follow and event["step_id"] == self.active_step_id
            ):
                self._refresh_log_and_details()

        def _on_command_finished(self, event: Dict[str, Any]) -> None:
            info = self._step_state.get(event["step_id"])
            if info is None:
                return
            info.setdefault("command", {})["returncode"] = event.get("returncode", 0)
            if self.selected_step_id == event["step_id"] or (
                self.auto_follow and event["step_id"] == self.active_step_id
            ):
                self._refresh_log_and_details()

        def _on_step_finished(self, event: Dict[str, Any]) -> None:
            step_id = event["step_id"]
            info = self._step_state.get(step_id)
            if info is None:
                return

            info["state"] = event.get("state", "success")
            info["summary"] = event.get("summary", "") or info.get("summary", "")
            info["duration"] = float(event.get("duration", 0.0) or 0.0)
            info["finished_at"] = event.get("finished_at", "done")
            if info["state"] == "failed":
                self.failed_step_id = step_id
                self.active_step_id = step_id
                if self.auto_follow:
                    self._select_step(step_id)

            node = self._nodes.get(step_id)
            if node is not None:
                node.set_label(self._node_label(step_id))

            if self.selected_step_id == step_id or (self.auto_follow and step_id == self.active_step_id):
                self._refresh_log_and_details()

        def _on_session_summary(self, event: Dict[str, Any]) -> None:
            state = event.get("state", "success")
            duration = float(event.get("duration", 0.0) or 0.0)
            if state == "success":
                self.sub_title = f"Completed in {duration:.2f}s"
            else:
                self.sub_title = f"Failed after {duration:.2f}s"

        def action_detach(self) -> None:
            self.detached = True
            self.exit(False)

        def action_focus_active(self) -> None:
            self.auto_follow = True
            self.sub_title = "Auto-follow on"
            if self.active_step_id:
                self._select_step(self.active_step_id)

        def action_toggle_auto_follow(self) -> None:
            self.auto_follow = not self.auto_follow
            self.sub_title = "Auto-follow on" if self.auto_follow else "Auto-follow off"
            if self.auto_follow and self.active_step_id:
                self._select_step(self.active_step_id)

        def action_toggle_selected(self) -> None:
            node = self.steps.cursor_node
            if node is None:
                return
            if node.is_expanded:
                node.collapse()
            else:
                node.expand()

        def on_tree_node_selected(self, event) -> None:  # pragma: no cover - exercised only in live UI
            if getattr(event.node, "data", None):
                self.selected_step_id = event.node.data
                self._refresh_log_and_details()

        def on_tree_node_highlighted(self, event) -> None:  # pragma: no cover - exercised only in live UI
            if not self.auto_follow and getattr(event.node, "data", None):
                self.selected_step_id = event.node.data
                self._refresh_log_and_details()

    app = ExecutionTextualApp(operation)
    app.run()

    if app.detached and app.worker_is_alive():
        session.add_renderer(RawOutputRenderer())

    app.join_worker()
    if app.error is not None:
        raise app.error
    return app.result
