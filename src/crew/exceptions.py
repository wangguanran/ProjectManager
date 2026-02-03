"""Custom exceptions for CrewAI workflow."""

from __future__ import annotations

from typing import Optional


class CrewWorkflowError(Exception):
    """Base exception for crew workflow errors."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TaskExecutionError(CrewWorkflowError):
    """Exception raised when a task execution fails."""

    def __init__(self, task_id: str, message: str, details: Optional[dict] = None):
        super().__init__(message, details)
        self.task_id = task_id


class AgentTimeoutError(CrewWorkflowError):
    """Exception raised when an agent times out."""

    def __init__(self, agent_role: str, message: str = "Agent execution timed out"):
        super().__init__(message, {"agent_role": agent_role})
        self.agent_role = agent_role


class ReviewFailedError(CrewWorkflowError):
    """Exception raised when code review fails."""

    def __init__(self, notes: str, details: Optional[dict] = None):
        super().__init__(f"Code review failed: {notes}", details)
        self.notes = notes


class TestExecutionError(CrewWorkflowError):
    """Exception raised when test execution fails."""

    def __init__(self, message: str, failures: Optional[list] = None):
        super().__init__(message, {"failures": failures or []})
        self.failures = failures or []


class ConfigurationError(CrewWorkflowError):
    """Exception raised for configuration errors."""

    pass


class LLMProviderError(CrewWorkflowError):
    """Exception raised when LLM provider fails."""

    def __init__(self, provider: str, message: str, details: Optional[dict] = None):
        super().__init__(f"LLM provider '{provider}' failed: {message}", details)
        self.provider = provider


class ConflictDetectedError(CrewWorkflowError):
    """Exception raised when conflicts are detected."""

    def __init__(self, conflicts: list, message: str = "Conflicts detected"):
        super().__init__(message, {"conflicts": conflicts})
        self.conflicts = conflicts


class MaxRetriesExceededError(CrewWorkflowError):
    """Exception raised when maximum retries are exceeded."""

    def __init__(self, step: str, attempts: int):
        super().__init__(f"Maximum retries exceeded for step '{step}' after {attempts} attempts")
        self.step = step
        self.attempts = attempts


__all__ = [
    "CrewWorkflowError",
    "TaskExecutionError",
    "AgentTimeoutError",
    "ReviewFailedError",
    "TestExecutionError",
    "ConfigurationError",
    "LLMProviderError",
    "ConflictDetectedError",
    "MaxRetriesExceededError",
]
