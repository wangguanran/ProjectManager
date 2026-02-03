"""Pytest fixtures for crew tests."""

import os
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import Mock

import pytest

from src.crew import LLMConfig, LLMProviderConfig


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def tasks_path(temp_dir: Path) -> str:
    """Get path to temporary tasks file."""
    return str(temp_dir / "tasks.md")


@pytest.fixture
def test_cases_path(temp_dir: Path) -> str:
    """Get path to temporary test cases file."""
    return str(temp_dir / "test_cases.md")


@pytest.fixture
def mock_llm():
    """Create a mock LLM."""
    return Mock()


@pytest.fixture
def mock_llm_config() -> LLMConfig:
    """Create a mock LLM configuration."""
    # Set dummy API key in environment for testing
    os.environ["TEST_API_KEY"] = "test_key_12345"

    provider = LLMProviderConfig(
        provider="minimax",
        model="test-model",
        api_key_env="TEST_API_KEY",
        base_url="https://test.api.com",
        temperature=0.5,
        max_tokens=2000,
    )

    return LLMConfig(
        primary=provider,
        enable_memory=False,  # Disable for tests
        enable_parallel=False,
        max_retries=2,
    )


@pytest.fixture
def sample_request_data() -> dict:
    """Sample request data for testing."""
    return {
        "request_type": "new_requirement",
        "title": "Add user login feature",
        "details": "Implement username and password authentication",
    }


@pytest.fixture(autouse=True)
def cleanup_env():
    """Cleanup test environment variables after each test."""
    yield
    # Remove test API key
    if "TEST_API_KEY" in os.environ:
        del os.environ["TEST_API_KEY"]
