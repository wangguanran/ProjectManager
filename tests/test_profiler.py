"""
Tests for profiler module.
"""

import os
import sys
import time
import pytest
from unittest.mock import patch, MagicMock


class TestProfilerFunctions:
    """Test cases for profiler functions."""

    def setup_method(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.profiler import func_time, func_cprofile, auto_profile

        self.func_time = func_time
        self.func_cprofile = func_cprofile
        self.auto_profile = auto_profile

    def test_func_time_decorator(self):
        """Test func_time decorator."""

        @self.func_time
        def test_function():
            time.sleep(0.01)  # Small delay to ensure measurable time
            return "test_result"

        result = test_function()
        assert result == "test_result"

    def test_func_cprofile_decorator(self):
        """Test func_cprofile decorator."""

        @self.func_cprofile
        def test_function():
            return "test_result"

        result = test_function()
        assert result == "test_result"

    def test_func_cprofile_with_exception(self):
        """Test func_cprofile decorator when stats printing fails."""

        @self.func_cprofile
        def test_function():
            return "test_result"

        with patch("src.profiler.pstats.Stats") as mock_stats:
            # Make stats printing fail
            mock_stats.side_effect = OSError("Test error")

            result = test_function()
            assert result == "test_result"


class TestAutoProfile:
    """Test cases for auto_profile decorator."""

    def setup_method(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.profiler import auto_profile

        self.auto_profile = auto_profile

    def test_auto_profile_class_decorator(self):
        """Test auto_profile class decorator."""

        @self.auto_profile
        class TestClass:
            def public_method(self):
                return "public_result"

            def _private_method(self):
                return "private_result"

            def __magic_method__(self):
                return "magic_result"

        # Create instance
        obj = TestClass()

        # Test that public methods are wrapped
        result = obj.public_method()
        assert result == "public_result"

        # Test that private methods are not wrapped
        result = obj._private_method()
        assert result == "private_result"

        # Test that magic methods are not wrapped
        result = obj.__magic_method__()
        assert result == "magic_result"

    def test_auto_profile_with_cprofile_enabled(self):
        """Test auto_profile with cProfile enabled."""
        # Enable cProfile
        import builtins

        builtins.ENABLE_CPROFILE = True

        @self.auto_profile
        class TestClass:
            def test_method(self):
                return "test_result"

        obj = TestClass()
        result = obj.test_method()
        assert result == "test_result"

        # Clean up
        delattr(builtins, "ENABLE_CPROFILE")

    def test_auto_profile_with_cprofile_disabled(self):
        """Test auto_profile with cProfile disabled."""
        # Ensure cProfile is disabled
        import builtins

        if hasattr(builtins, "ENABLE_CPROFILE"):
            delattr(builtins, "ENABLE_CPROFILE")

        @self.auto_profile
        class TestClass:
            def test_method(self):
                return "test_result"

        obj = TestClass()
        result = obj.test_method()
        assert result == "test_result"

    def test_auto_profile_with_non_callable_attributes(self):
        """Test auto_profile with non-callable attributes."""

        @self.auto_profile
        class TestClass:
            attribute = "not_callable"

            def method(self):
                return "method_result"

        obj = TestClass()
        assert obj.attribute == "not_callable"
        result = obj.method()
        assert result == "method_result"

    def test_auto_profile_with_multiple_methods(self):
        """Test auto_profile with multiple methods."""

        @self.auto_profile
        class TestClass:
            def method1(self):
                return "result1"

            def method2(self):
                return "result2"

            def method3(self):
                return "result3"

        obj = TestClass()
        assert obj.method1() == "result1"
        assert obj.method2() == "result2"
        assert obj.method3() == "result3"

    def test_auto_profile_method_arguments(self):
        """Test auto_profile with method arguments."""

        @self.auto_profile
        class TestClass:
            def method_with_args(self, arg1, arg2, kwarg1=None):
                return f"{arg1}_{arg2}_{kwarg1}"

        obj = TestClass()
        result = obj.method_with_args("a", "b", kwarg1="c")
        assert result == "a_b_c"

        result = obj.method_with_args("x", "y")
        assert result == "x_y_None"

    def test_auto_profile_method_exceptions(self):
        """Test auto_profile with method that raises exceptions."""

        @self.auto_profile
        class TestClass:
            def method_with_exception(self):
                raise ValueError("Test exception")

        obj = TestClass()
        with pytest.raises(ValueError, match="Test exception"):
            obj.method_with_exception()


class TestProfilerIntegration:
    """Integration tests for profiler functionality."""

    def setup_method(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.profiler import func_time, auto_profile

        self.func_time = func_time
        self.auto_profile = auto_profile

    def test_profiler_with_real_timing(self):
        """Test that profiler actually measures time."""

        @self.func_time
        def slow_function():
            time.sleep(0.1)
            return "done"

        start_time = time.time()
        result = slow_function()
        end_time = time.time()

        assert result == "done"
        # Function should have taken at least 0.1 seconds
        assert end_time - start_time >= 0.1

    def test_profiler_with_fast_function(self):
        """Test profiler with very fast function."""

        @self.func_time
        def fast_function():
            return "fast"

        result = fast_function()
        assert result == "fast"

    def test_profiler_with_class_methods(self):
        """Test profiler with class methods."""

        @self.auto_profile
        class PerformanceTestClass:
            def __init__(self):
                self.counter = 0

            def increment(self):
                self.counter += 1
                return self.counter

            def reset(self):
                self.counter = 0
                return self.counter

        obj = PerformanceTestClass()
        assert obj.increment() == 1
        assert obj.increment() == 2
        assert obj.reset() == 0
        assert obj.increment() == 1
