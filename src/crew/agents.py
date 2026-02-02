"""Crew agents for the workflow."""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Callable, List, Optional

from src.log_manager import log

from .models import CrewRequest, ReviewResult, Task, TaskStatus, TestCase


class RequirementAnalysisAgent:
    """Agent A: requirement analysis and user interaction."""

    def __init__(self, prompt_fn: Optional[Callable[[str], str]] = None):
        self.prompt_fn = prompt_fn or (lambda msg: input(msg))

    def confirm_request(self, request: CrewRequest) -> CrewRequest:
        if request.confirmed:
            return request
        answer = self.prompt_fn(
            f"Confirm request '{request.title}' (type 'yes' to confirm, anything else to reject): "
        ).strip()
        request.confirmed = answer.lower() == "yes"
        return request

    def generate_test_cases(self, request: CrewRequest) -> List[TestCase]:
        if request.request_type == request.request_type.NEW_REQUIREMENT:
            return [
                TestCase(
                    case_id="REQ-001",
                    title=f"{request.title} basic flow",
                    steps=["Follow the documented steps for the new requirement"],
                    expected=["Requirement behaves as specified"],
                )
            ]
        if request.request_type == request.request_type.BUG:
            return [
                TestCase(
                    case_id="BUG-001",
                    title=f"{request.title} regression",
                    steps=["Reproduce the reported bug using provided steps"],
                    expected=["Bug is reproduced in current version"],
                )
            ]
        return [
            TestCase(
                case_id="OPT-001",
                title=f"{request.title} optimization verification",
                steps=["Execute the optimized flow"],
                expected=["Performance or maintainability is improved without regressions"],
            )
        ]

    def check_conflicts(self, request: CrewRequest, existing_cases: List[TestCase]) -> bool:
        """Return True if a conflict is detected."""
        for case in existing_cases:
            if request.title.lower() in case.title.lower():
                return True
        return False

    def analyze_bug(self, request: CrewRequest) -> str:
        return "bug: requires confirmation whether blackbox or whitebox cases are missing"

    def analyze_optimization(self, request: CrewRequest) -> str:
        return "optimization: restrict changes to internal logic and whitebox tests"

    def dispatch_to_architect(self, request: CrewRequest, test_cases: List[TestCase]) -> dict:
        log.info("Dispatching to architect: %s", request.title)
        return {"request": request, "test_cases": test_cases}


class ArchitectAgent:
    """Agent B: break down tasks and assign to engineer."""

    def __init__(self, task_writer: Callable[[List[Task]], None]):
        self.task_writer = task_writer

    def decompose(self, request: CrewRequest, test_cases: List[TestCase]) -> List[Task]:
        tasks = [
            Task(
                task_id="T-001",
                title=request.title,
                description=request.details,
                assignee="C",
                status=TaskStatus.TODO,
                metadata={"test_cases": ",".join([case.case_id for case in test_cases])},
            )
        ]
        return tasks

    def assign(self, tasks: List[Task]) -> List[Task]:
        self.task_writer(tasks)
        return tasks


class CodeEngineerAgent:
    """Agent C: implement code changes for the tasks."""

    def implement(self, tasks: List[Task]) -> List[Task]:
        for task in tasks:
            task.status = TaskStatus.IN_PROGRESS
        return tasks


class ReviewEngineerAgent:
    """Agent D: review code changes."""

    def review(self, tasks: List[Task]) -> ReviewResult:
        for task in tasks:
            if task.status != TaskStatus.IN_PROGRESS:
                return ReviewResult(False, "Task not in progress")
        return ReviewResult(True, "Approved")


class TestCaseEngineerAgent:
    """Agent E: write test cases (blackbox then whitebox)."""

    def __init__(self, test_writer: Callable[[List[TestCase]], None]):
        self.test_writer = test_writer

    def write_tests(self, test_cases: List[TestCase]) -> None:
        self.test_writer(test_cases)


class TestExecutionAgent:
    """Agent F: execute test suite and validate coverage."""

    def __init__(self, runner: Callable[[], bool]):
        self.runner = runner

    def execute(self) -> bool:
        return self.runner()


class TaskTrackerAgent:
    """Agent A final step: update tasks and summarize commit message."""

    def __init__(self, task_updater: Callable[[List[Task]], None]):
        self.task_updater = task_updater

    def close_tasks(self, tasks: List[Task]) -> None:
        for task in tasks:
            task.status = TaskStatus.DONE
        self.task_updater(tasks)

    @staticmethod
    def generate_commit_message(tasks: List[Task]) -> str:
        titles = ", ".join(task.title for task in tasks)
        return f"feat(crew): complete {titles}"


class TaskStore:
    """Simple markdown-backed task store."""

    def __init__(self, path: str):
        self.path = path

    def _ensure_file(self) -> None:
        if not os.path.exists(self.path):
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("# Tasks\n\n| ID | Title | Assignee | Status | Created | Updated | Metadata |\n")
                f.write("| --- | --- | --- | --- | --- | --- | --- |\n")

    def write(self, tasks: List[Task]) -> None:
        self._ensure_file()
        with open(self.path, "a", encoding="utf-8") as f:
            for task in tasks:
                meta = ",".join([f"{k}={v}" for k, v in task.metadata.items()])
                f.write(
                    f"| {task.task_id} | {task.title} | {task.assignee} | {task.status.value} | "
                    f"{task.created_at} | {task.updated_at} | {meta} |\n"
                )

    def update(self, tasks: List[Task]) -> None:
        # Simple implementation: append updates to keep an audit trail.
        self.write(tasks)


class TestCaseStore:
    """Append-only store for generated test cases."""

    def __init__(self, path: str):
        self.path = path

    def load_existing(self, path: str) -> List[TestCase]:
        if not os.path.exists(path):
            return []
        cases: List[TestCase] = []
        current: Optional[TestCase] = None
        mode: Optional[str] = None
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if line.startswith("## "):
                    if current:
                        cases.append(current)
                    header = line[3:]
                    parts = header.split(" ", 1)
                    case_id = parts[0].strip()
                    title = parts[1].strip() if len(parts) > 1 else ""
                    current = TestCase(case_id=case_id, title=title, steps=[], expected=[])
                    mode = None
                    continue
                if not current:
                    continue
                if line.startswith("- Scope:"):
                    current.scope = line.replace("- Scope:", "", 1).strip()
                    continue
                if line.startswith("- Type:"):
                    current.case_type = line.replace("- Type:", "", 1).strip()
                    continue
                if line.startswith("- Steps"):
                    mode = "steps"
                    continue
                if line.startswith("- Expected"):
                    mode = "expected"
                    continue
                if line.startswith("- "):
                    if mode == "steps":
                        current.steps.append(line.replace("- ", "", 1).strip())
                    elif mode == "expected":
                        current.expected.append(line.replace("- ", "", 1).strip())
        if current:
            cases.append(current)
        return cases

    def write(self, test_cases: List[TestCase]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            for case in test_cases:
                f.write(f"## {case.case_id} {case.title}\n")
                f.write(f"- Scope: {case.scope}\n")
                f.write(f"- Type: {case.case_type}\n")
                f.write("- Steps:\n")
                for step in case.steps:
                    f.write(f"  - {step}\n")
                f.write("- Expected:\n")
                for expected in case.expected:
                    f.write(f"  - {expected}\n")
                f.write("\n")

    @staticmethod
    def load_existing(path: str) -> List[TestCase]:
        # Minimal parser: we only use this for conflict checks by title.
        if not os.path.exists(path):
            return []
        test_cases: List[TestCase] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("## "):
                    _, rest = line.split("## ", 1)
                    parts = rest.strip().split(" ", 1)
                    if len(parts) == 2:
                        case_id, title = parts
                    else:
                        case_id = parts[0]
                        title = parts[0]
                    test_cases.append(TestCase(case_id=case_id, title=title, steps=[], expected=[]))
        return test_cases


__all__ = [
    "RequirementAnalysisAgent",
    "ArchitectAgent",
    "CodeEngineerAgent",
    "ReviewEngineerAgent",
    "TestCaseEngineerAgent",
    "TestExecutionAgent",
    "TaskTrackerAgent",
    "TaskStore",
    "TestCaseStore",
]
