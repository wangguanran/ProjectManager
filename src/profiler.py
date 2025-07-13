"""
Profiling decorators for performance analysis.
"""

import builtins
import cProfile
import io
import pstats
import time
from functools import wraps

from src.log_manager import log
from src.utils import path_from_root

CPROFILE_PATH = path_from_root(".cache", "cprofile")
PROFILE_DUMP_NAME = "profile_dump"


def func_time(func):
    """Decorator to measure function execution time."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        log.debug("%s took %f seconds", func.__name__, end - start)
        return result

    return wrapper


def func_cprofile(func):
    """Decorator to profile a function using cProfile and log stats."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        profile = cProfile.Profile()
        try:
            profile.enable()
            result = func(*args, **kwargs)
            profile.disable()
            return result
        finally:
            try:
                s = io.StringIO()
                ps = pstats.Stats(profile, stream=s)
                ps.sort_stats("time").print_stats()  # print all
                log.debug("cProfile stats for %s:\n%s", func.__name__, s.getvalue())
            except (OSError, IOError) as exc:
                log.exception("fail to print cProfile stats: %s", exc)

    return wrapper


def auto_profile(cls):
    """
    Class decorator: automatically decorate all public instance methods with func_time and (optionally) func_cprofile, dynamically at call time.
    Ensures that staticmethod/classmethod wrapper types are not lost.
    """

    def make_wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            enable_cprofile = getattr(builtins, "ENABLE_CPROFILE", False)
            if enable_cprofile:
                return func_time(func_cprofile(func))(*args, **kwargs)
            return func_time(func)(*args, **kwargs)

        return wrapper

    for attr_name, attr_value in cls.__dict__.items():
        if attr_name.startswith("__"):
            continue
        if isinstance(attr_value, staticmethod):
            func = attr_value.__func__
            wrapped = staticmethod(make_wrapper(func))
        elif isinstance(attr_value, classmethod):
            func = attr_value.__func__
            wrapped = classmethod(make_wrapper(func))
        elif callable(attr_value):
            wrapped = make_wrapper(attr_value)
        else:
            continue
        setattr(cls, attr_name, wrapped)
    return cls
