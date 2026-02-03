"""Tests for crew models."""

import pytest

from src.crew.models import CrewRequest, RequestType, Task, TaskStatus, TestCase, WorkflowResult


class TestCrewRequest:
    """Tests for CrewRequest model."""

    def test_create_new_requirement(self):
        """Test creating a new requirement request."""
        request = CrewRequest(
            request_type=RequestType.NEW_REQUIREMENT,
            title="Add login feature",
            details="Implement user authentication",
        )
        assert request.request_type == RequestType.NEW_REQUIREMENT
        assert request.title == "Add login feature"
        assert not request.confirmed
        assert isinstance(request.metadata, dict)

    def test_create_bug_request(self):
        """Test creating a bug fix request."""
        request = CrewRequest(
            request_type=RequestType.BUG,
            title="Fix login issue",
            details="Login fails with special characters",
        )
        assert request.request_type == RequestType.BUG

    def test_create_optimization_request(self):
        """Test creating an optimization request."""
        request = CrewRequest(
            request_type=RequestType.OPTIMIZATION,
            title="Optimize database queries",
            details="Reduce query count",
        )
        assert request.request_type == RequestType.OPTIMIZATION


class TestTask:
    """Tests for Task model."""

    def test_create_task(self):
        """Test creating a task."""
        task = Task(
            task_id="T-001",
            title="Implement login",
            description="Create login form and authentication",
            assignee="C",
        )
        assert task.task_id == "T-001"
        assert task.status == TaskStatus.TODO
        assert task.assignee == "C"
        assert task.created_at
        assert task.updated_at

    def test_task_with_metadata(self):
        """Test task with metadata."""
        task = Task(
            task_id="T-002",
            title="Add tests",
            description="Write unit tests",
            assignee="C",
            metadata={"test_cases": "TC-001,TC-002"},
        )
        assert task.metadata["test_cases"] == "TC-001,TC-002"


class TestTestCase:
    """Tests for TestCase model."""

    def test_create_blackbox_test_case(self):
        """Test creating a blackbox test case."""
        case = TestCase(
            case_id="TC-001",
            title="Login with valid credentials",
            steps=["Navigate to login page", "Enter username and password", "Click login"],
            expected=["User is logged in", "Dashboard is displayed"],
            scope="blackbox",
        )
        assert case.case_id == "TC-001"
        assert case.scope == "blackbox"
        assert len(case.steps) == 3
        assert len(case.expected) == 2

    def test_create_whitebox_test_case(self):
        """Test creating a whitebox test case."""
        case = TestCase(
            case_id="TC-002",
            title="Test authentication logic",
            steps=["Call authenticate() with valid credentials"],
            expected=["Returns user object", "Session is created"],
            scope="whitebox",
        )
        assert case.scope == "whitebox"


class TestWorkflowResult:
    """Tests for WorkflowResult model."""

    def test_successful_result(self):
        """Test successful workflow result."""
        task = Task(
            task_id="T-001",
            title="Test task",
            description="Description",
            assignee="C",
        )
        result = WorkflowResult(
            success=True, message="Workflow completed", tasks=[task], tests_added=[]
        )
        assert result.success
        assert len(result.tasks) == 1
        assert result.tasks[0].task_id == "T-001"

    def test_failed_result(self):
        """Test failed workflow result."""
        result = WorkflowResult(success=False, message="Review failed")
        assert not result.success
        assert "Review failed" in result.message
        assert len(result.tasks) == 0
