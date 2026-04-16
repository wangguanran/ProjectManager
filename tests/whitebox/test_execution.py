"""Tests for execution renderers and render-mode helpers."""

from __future__ import annotations

import io
import re

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
