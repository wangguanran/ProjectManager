"""Automatic test execution for CrewAI workflow."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from src.log_manager import log


@dataclass
class TestResult:
    """Result of test execution."""

    passed: bool
    total: int
    failed: int
    skipped: int
    duration: float
    output: str
    failures: List[str]


class PytestRunner:
    """Pytest test runner."""

    def __init__(self, test_dir: str = "tests", extra_args: Optional[List[str]] = None):
        """Initialize pytest runner.

        Args:
            test_dir: Directory containing tests
            extra_args: Additional pytest arguments
        """
        self.test_dir = test_dir
        self.extra_args = extra_args or []

    def run(self, test_pattern: Optional[str] = None) -> TestResult:
        """Run tests with pytest.

        Args:
            test_pattern: Optional pattern to filter tests (e.g., "test_models.py")

        Returns:
            TestResult: Test execution result
        """
        cmd = ["pytest", self.test_dir, "-v", "--tb=short", "--color=no"]

        if test_pattern:
            cmd.extend(["-k", test_pattern])

        cmd.extend(self.extra_args)

        log.info(f"Running tests: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300, check=False
            )

            output = result.stdout + "\n" + result.stderr
            passed = result.returncode == 0

            # Parse pytest output
            total, failed, skipped, duration = self._parse_pytest_output(output)
            failures = self._extract_failures(output) if not passed else []

            return TestResult(
                passed=passed,
                total=total,
                failed=failed,
                skipped=skipped,
                duration=duration,
                output=output,
                failures=failures,
            )

        except subprocess.TimeoutExpired:
            log.error("Test execution timed out")
            return TestResult(
                passed=False,
                total=0,
                failed=0,
                skipped=0,
                duration=300.0,
                output="Test execution timed out after 300 seconds",
                failures=["Timeout"],
            )
        except FileNotFoundError:
            log.error("pytest not found. Install with: pip install pytest")
            return TestResult(
                passed=False,
                total=0,
                failed=0,
                skipped=0,
                duration=0.0,
                output="pytest not found",
                failures=["pytest not installed"],
            )
        except Exception as exc:
            log.error(f"Test execution failed: {exc}")
            return TestResult(
                passed=False,
                total=0,
                failed=0,
                skipped=0,
                duration=0.0,
                output=str(exc),
                failures=[str(exc)],
            )

    def _parse_pytest_output(self, output: str) -> tuple[int, int, int, float]:
        """Parse pytest summary line."""
        # Example: "=== 10 passed, 2 failed, 1 skipped in 5.23s ==="
        total = 0
        failed = 0
        skipped = 0
        duration = 0.0

        for line in output.split("\n"):
            if " passed" in line or " failed" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "passed" and i > 0:
                        total = int(parts[i - 1])
                    elif part == "failed" and i > 0:
                        failed = int(parts[i - 1])
                    elif part == "skipped" and i > 0:
                        skipped = int(parts[i - 1])
                    elif "in" in part and i + 1 < len(parts):
                        try:
                            duration = float(parts[i + 1].rstrip("s"))
                        except ValueError:
                            pass

        return total, failed, skipped, duration

    def _extract_failures(self, output: str) -> List[str]:
        """Extract failure descriptions from pytest output."""
        failures = []
        in_failure = False
        current_failure = []

        for line in output.split("\n"):
            if line.startswith("FAILED "):
                in_failure = True
                current_failure = [line]
            elif in_failure:
                if line.startswith("=") or line.startswith("PASSED "):
                    if current_failure:
                        failures.append("\n".join(current_failure))
                        current_failure = []
                    in_failure = False
                else:
                    current_failure.append(line)

        if current_failure:
            failures.append("\n".join(current_failure))

        return failures[:10]  # Limit to first 10 failures


class UnittestRunner:
    """Python unittest runner."""

    def __init__(self, test_dir: str = "tests"):
        """Initialize unittest runner."""
        self.test_dir = test_dir

    def run(self, test_pattern: Optional[str] = None) -> TestResult:
        """Run tests with unittest discover."""
        cmd = ["python", "-m", "unittest", "discover", "-s", self.test_dir, "-v"]

        if test_pattern:
            cmd.extend(["-p", test_pattern])

        log.info(f"Running tests: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300, check=False
            )

            output = result.stdout + "\n" + result.stderr
            passed = result.returncode == 0

            # Parse unittest output (simpler than pytest)
            total, failed = self._parse_unittest_output(output)

            return TestResult(
                passed=passed,
                total=total,
                failed=failed,
                skipped=0,
                duration=0.0,
                output=output,
                failures=[] if passed else [output[-1000:]],  # Last 1000 chars
            )

        except Exception as exc:
            log.error(f"Test execution failed: {exc}")
            return TestResult(
                passed=False,
                total=0,
                failed=0,
                skipped=0,
                duration=0.0,
                output=str(exc),
                failures=[str(exc)],
            )

    def _parse_unittest_output(self, output: str) -> tuple[int, int]:
        """Parse unittest output."""
        # Example: "Ran 10 tests in 5.234s"
        # Example: "FAILED (failures=2)"
        total = 0
        failed = 0

        for line in output.split("\n"):
            if line.startswith("Ran "):
                parts = line.split()
                if len(parts) >= 2:
                    total = int(parts[1])
            elif "FAILED" in line and "failures=" in line:
                start = line.index("failures=") + 9
                end = line.index(")", start)
                failed = int(line[start:end])

        return total, failed


def create_test_runner(framework: str = "pytest", **kwargs) -> PytestRunner | UnittestRunner:
    """Create a test runner based on framework.

    Args:
        framework: Test framework to use ("pytest" or "unittest")
        **kwargs: Additional arguments for the runner

    Returns:
        Test runner instance
    """
    if framework == "pytest":
        return PytestRunner(**kwargs)
    elif framework == "unittest":
        return UnittestRunner(**kwargs)
    else:
        raise ValueError(f"Unsupported test framework: {framework}")


__all__ = ["TestResult", "PytestRunner", "UnittestRunner", "create_test_runner"]
