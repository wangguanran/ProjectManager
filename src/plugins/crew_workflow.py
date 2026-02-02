"""Crew workflow CLI operations."""

from __future__ import annotations

import json
from typing import Dict

from src.log_manager import log
from src.operations.registry import register

from src.crew import CrewRequest, CrewWorkflow, RequestType, default_tasks_path, default_test_cases_path


def _load_request(payload_path: str | None, title: str | None, details: str | None, req_type: str | None):
    if payload_path:
        with open(payload_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return CrewRequest(
            request_type=RequestType(data["request_type"]),
            title=data["title"],
            details=data.get("details", ""),
            confirmed=bool(data.get("confirmed", False)),
            metadata=data.get("metadata", {}),
        )
    if not title or not req_type:
        raise ValueError("request payload requires --title and --request-type when --request is not provided")
    return CrewRequest(
        request_type=RequestType(req_type),
        title=title,
        details=details or "",
        confirmed=False,
        metadata={},
    )


@register("crew_run", desc="Run Crew workflow for a request")
def crew_run(
    env: Dict,
    projects_info: Dict,
    name: str | None = None,
    request: str | None = None,
    title: str | None = None,
    details: str | None = None,
    request_type: str | None = None,
    auto_confirm: bool = False,
) -> bool:
    """Run the Crew workflow. Provide --request JSON or --title/--request-type."""
    _ = env, projects_info, name  # name is required by CLI but not used
    try:
        crew_request = _load_request(request, title, details, request_type)
    except ValueError as exc:
        log.error(str(exc))
        return False

    workflow = CrewWorkflow(
        tasks_path=default_tasks_path(),
        test_cases_path=default_test_cases_path(),
    )
    result = workflow.run(crew_request, auto_confirm=auto_confirm)
    if not result.success:
        log.error(result.message)
        return False

    log.info(result.message)
    return True
