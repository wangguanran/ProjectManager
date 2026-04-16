"""Tests for execution renderers and render-mode helpers."""

from __future__ import annotations

import io
import re

from rich.console import Console

from src.execution import BuildkitOutputRenderer


def test_buildkit_output_renderer_renders_finished_cached_step() -> None:
    stream = io.StringIO()
    renderer = BuildkitOutputRenderer(stream=stream, dynamic=False)

    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_apply",
            "title": "po apply: projA",
            "parent_id": None,
        }
    )
    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_apply.commits",
            "title": "Apply commits",
            "parent_id": "operation.po_apply",
        }
    )
    renderer.on_event(
        {
            "type": "step_log",
            "step_id": "operation.po_apply.commits",
            "text": "po 'po_base' already applied for repo 'repo1', skipping commit '0001.patch'",
            "kind": "info",
        }
    )
    renderer.on_event(
        {
            "type": "step_finished",
            "step_id": "operation.po_apply.commits",
            "state": "success",
            "duration": 0.2,
            "summary": "",
        }
    )
    renderer.on_event(
        {
            "type": "session_summary",
            "title": "po apply: projA",
            "state": "success",
            "duration": 0.3,
        }
    )

    output = stream.getvalue()
    assert "[+] po apply: projA 0.3s (1/1) FINISHED" in output
    assert "=> [1/1] Apply commits" in output
    assert "CACHED" in output


def test_buildkit_output_renderer_renders_root_logs_without_child_steps() -> None:
    stream = io.StringIO()
    renderer = BuildkitOutputRenderer(stream=stream, dynamic=False)

    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_list",
            "title": "po list: projA",
            "parent_id": None,
        }
    )
    renderer.on_event(
        {
            "type": "step_log",
            "step_id": "operation.po_list",
            "text": "listing patch overrides for projA",
            "kind": "info",
        }
    )
    renderer.on_event(
        {
            "type": "session_summary",
            "title": "po list: projA",
            "state": "success",
            "duration": 0.1,
        }
    )

    output = stream.getvalue()
    assert "[+] po list: projA 0.1s FINISHED" in output
    assert "=> => listing patch overrides for projA" in output


def test_buildkit_output_renderer_right_aligns_status_column() -> None:
    stream = io.StringIO()
    renderer = BuildkitOutputRenderer(stream=stream, dynamic=False, console_width=80)

    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_apply",
            "title": "po apply: projA",
            "parent_id": None,
        }
    )
    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_apply.commits",
            "title": "Apply commits",
            "parent_id": "operation.po_apply",
        }
    )
    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_apply.finalize",
            "title": "Finalize applied records",
            "parent_id": "operation.po_apply",
        }
    )
    renderer.on_event(
        {
            "type": "step_finished",
            "step_id": "operation.po_apply.commits",
            "state": "success",
            "duration": 0.2,
            "summary": "",
        }
    )
    renderer.on_event(
        {
            "type": "step_finished",
            "step_id": "operation.po_apply.finalize",
            "state": "success",
            "duration": 12.3,
            "summary": "",
        }
    )
    renderer.on_event(
        {
            "type": "session_summary",
            "title": "po apply: projA",
            "state": "success",
            "duration": 12.5,
        }
    )

    lines = [line for line in stream.getvalue().splitlines() if "=> [" in line]
    assert len(lines) == 2
    commit_match = re.search(r"(0\.2s)\s*$", lines[0])
    finalize_match = re.search(r"(12\.3s)\s*$", lines[1])
    assert commit_match is not None
    assert finalize_match is not None
    assert commit_match.end(1) == len(lines[0])
    assert finalize_match.end(1) == len(lines[1])


def test_buildkit_output_renderer_enables_live_auto_refresh(monkeypatch) -> None:
    created = {}

    class FakeLive:
        def __init__(self, renderable, **kwargs):
            created["kwargs"] = kwargs
            self.renderable = renderable
            self.started = False

        def start(self):
            self.started = True
            created["started"] = True

        def update(self, renderable, refresh=True):
            self.renderable = renderable
            created["updated"] = refresh

        def refresh(self):
            created["refreshed"] = True

        def stop(self):
            created["stopped"] = True

    monkeypatch.setattr("rich.live.Live", FakeLive)

    renderer = BuildkitOutputRenderer(stream=io.StringIO(), dynamic=True, refresh_per_second=12.0)
    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_revert",
            "title": "po revert: projA",
            "parent_id": None,
        }
    )
    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_revert.commits",
            "title": "Revert commits",
            "parent_id": "operation.po_revert",
        }
    )

    assert created["kwargs"]["auto_refresh"] is True
    assert created["kwargs"]["refresh_per_second"] == 12.0
    assert created["kwargs"]["transient"] is False
    assert created["started"] is True


def test_buildkit_live_renderable_recomputes_running_durations(monkeypatch) -> None:
    from rich.console import Console

    renderer = BuildkitOutputRenderer(stream=io.StringIO(), dynamic=False, console_width=80)
    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_revert",
            "title": "po revert: projA",
            "parent_id": None,
        }
    )
    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_revert.commits",
            "title": "Revert commits",
            "parent_id": "operation.po_revert",
        }
    )

    renderer._session_started_at = 0.0
    renderer._steps["operation.po_revert.commits"]["started_at_mono"] = 0.0

    first = io.StringIO()
    second = io.StringIO()

    monkeypatch.setattr("src.execution.time.monotonic", lambda: 1.2)
    Console(file=first, width=80, force_terminal=False, highlight=False).print(renderer._live_renderable)

    monkeypatch.setattr("src.execution.time.monotonic", lambda: 2.4)
    Console(file=second, width=80, force_terminal=False, highlight=False).print(renderer._live_renderable)

    assert "[+] po revert: projA 1.2s (0/1)" in first.getvalue()
    assert "1.2s" in first.getvalue()
    assert "[+] po revert: projA 2.4s (0/1)" in second.getvalue()
    assert "2.4s" in second.getvalue()


def test_buildkit_output_renderer_wraps_long_failed_logs() -> None:
    stream = io.StringIO()
    renderer = BuildkitOutputRenderer(stream=stream, dynamic=False, console_width=72)

    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_apply",
            "title": "po apply: projA",
            "parent_id": None,
        }
    )
    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_apply.commits",
            "title": "Apply commits",
            "parent_id": "operation.po_apply",
        }
    )
    renderer.on_event(
        {
            "type": "step_log",
            "step_id": "operation.po_apply.commits",
            "text": "Failed to apply commit patch '/very/long/path/0001.patch': fatal: previous rebase directory .git/rebase-apply still exists but mbox given.",
            "kind": "error",
        }
    )
    renderer.on_event(
        {
            "type": "step_finished",
            "step_id": "operation.po_apply.commits",
            "state": "failed",
            "duration": 1.2,
            "summary": "Operation returned failure status.",
        }
    )
    renderer.on_event(
        {
            "type": "session_summary",
            "title": "po apply: projA",
            "state": "failed",
            "duration": 1.5,
        }
    )

    output = stream.getvalue()
    assert "rebase directory .git/rebase-apply still exists" in output
    assert "mbox" in output
    assert "given." in output


def test_buildkit_output_renderer_keeps_raw_failure_stderr_visible() -> None:
    stream = io.StringIO()
    renderer = BuildkitOutputRenderer(stream=stream, dynamic=False, console_width=96)

    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_apply",
            "title": "po apply: projA",
            "parent_id": None,
        }
    )
    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_apply.commits",
            "title": "Apply commits",
            "parent_id": "operation.po_apply",
        }
    )

    for idx in range(6):
        renderer.on_event(
            {
                "type": "step_log",
                "step_id": "operation.po_apply.commits",
                "text": f"Commit patch '000{idx}.patch' already applied; skipping.",
                "kind": "info",
            }
        )

    renderer.on_event(
        {
            "type": "step_log",
            "step_id": "operation.po_apply.commits",
            "text": "fatal: previous rebase directory .git/rebase-apply still exists but mbox given.",
            "kind": "stderr",
        }
    )
    renderer.on_event(
        {
            "type": "step_log",
            "step_id": "operation.po_apply.commits",
            "text": "Failed to apply commit patch '/very/long/path/0007.patch': [len=80 tail=fatal: previous rebase directory .git/rebase-apply still exists but mbox given.]",
            "kind": "error",
        }
    )
    renderer.on_event(
        {
            "type": "step_log",
            "step_id": "operation.po_apply.commits",
            "text": "po apply aborted due to error in po: 'po_base'",
            "kind": "error",
        }
    )
    renderer.on_event(
        {
            "type": "step_finished",
            "step_id": "operation.po_apply.commits",
            "state": "failed",
            "duration": 2.0,
            "summary": "Operation returned failure status.",
        }
    )
    renderer.on_event(
        {
            "type": "session_summary",
            "title": "po apply: projA",
            "state": "failed",
            "duration": 2.2,
        }
    )

    output = stream.getvalue()
    assert "fatal: previous rebase directory .git/rebase-apply still exists but mbox" in output
    assert "po apply aborted due to error in po: 'po_base'" in output


def test_buildkit_output_renderer_shows_running_command_detail(monkeypatch) -> None:
    renderer = BuildkitOutputRenderer(stream=io.StringIO(), dynamic=False, console_width=100)

    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_apply",
            "title": "po apply: projA",
            "parent_id": None,
        }
    )
    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_apply.commits",
            "title": "Apply commits",
            "parent_id": "operation.po_apply",
        }
    )
    monkeypatch.setattr("src.execution.time.monotonic", lambda: 12.4)
    renderer.on_event(
        {
            "type": "step_command_started",
            "step_id": "operation.po_apply.commits",
            "description": "Apply commit patch 0001.patch to repoA",
            "command": "git am 0001.patch",
            "cwd": "/tmp/repoA",
        }
    )
    renderer._steps["operation.po_apply.commits"]["active_command"]["started_at_mono"] = 10.0

    output = io.StringIO()
    Console(file=output, width=100, force_terminal=False, highlight=False).print(renderer._live_renderable)

    rendered = output.getvalue()
    assert "=> => RUN Apply commit patch 0001.patch to repoA" in rendered
    assert re.search(r"2\.4s\s*$", rendered.splitlines()[-1]) is not None


def test_buildkit_live_renderable_auto_trims_details_to_viewport_height() -> None:
    renderer = BuildkitOutputRenderer(stream=io.StringIO(), dynamic=True, console_width=80)

    renderer.on_event(
        {
            "type": "step_started",
            "step_id": "operation.po_apply",
            "title": "po apply: projA",
            "parent_id": None,
        }
    )
    for index in range(2):
        step_id = f"operation.po_apply.step{index}"
        renderer.on_event(
            {
                "type": "step_started",
                "step_id": step_id,
                "title": f"Step {index}",
                "parent_id": "operation.po_apply",
            }
        )
        renderer.on_event(
            {
                "type": "step_command_started",
                "step_id": step_id,
                "description": f"Apply detail {index}",
                "command": f"cmd-{index}",
                "cwd": "/tmp",
            }
        )
        renderer.on_event(
            {
                "type": "step_command_finished",
                "step_id": step_id,
                "description": f"Apply detail {index}",
                "command": f"cmd-{index}",
                "cwd": "/tmp",
                "returncode": 0,
            }
        )
        renderer.on_event(
            {
                "type": "step_finished",
                "step_id": step_id,
                "state": "success",
                "duration": 0.2,
                "summary": "",
            }
        )

    output = io.StringIO()
    Console(file=output, width=80, height=6, force_terminal=False, highlight=False).print(renderer._live_renderable)

    rendered = output.getvalue()
    assert "=> => DONE Apply detail 0" in rendered
    assert "=> => DONE Apply detail 1" not in rendered
