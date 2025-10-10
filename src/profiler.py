"""Runtime profiling helpers used by the CLI entry points."""

from __future__ import annotations

import builtins
import cProfile
import io
import pstats
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar, cast

from src.log_manager import log
from src.utils import path_from_root

CPROFILE_PATH = Path(path_from_root(".cache", "cprofile"))
PROFILE_DUMP_NAME = "profile_dump"

F = TypeVar("F", bound=Callable[..., Any])


def func_time(func: F) -> F:
    """Decorator to measure function execution time."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            duration = time.perf_counter() - start
            log.debug("%s took %f seconds", func.__name__, duration)

    return cast(F, wrapper)


def func_cprofile(func: F) -> F:
    """Decorator to profile a function using cProfile and log stats."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        enable_cprofile = getattr(builtins, "ENABLE_CPROFILE", False)
        if enable_cprofile:
            profile = cProfile.Profile()
            profile.enable()
            try:
                result = func(*args, **kwargs)
            finally:
                profile.disable()
                try:
                    CPROFILE_PATH.mkdir(parents=True, exist_ok=True)
                    s = io.StringIO()
                    stats = pstats.Stats(profile, stream=s)
                    stats.sort_stats("time").print_stats()
                    log.debug("cProfile stats for %s:\n%s", func.__name__, s.getvalue())
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    dump_path = CPROFILE_PATH / f"{PROFILE_DUMP_NAME}_{func.__name__}_{timestamp}.prof"
                    profile.dump_stats(dump_path)
                    log.debug("cProfile dump written to %s", dump_path)
                except (OSError, IOError) as exc:
                    log.exception("fail to print cProfile stats: %s", exc)
            return result
        return func(*args, **kwargs)

    return cast(F, wrapper)


def auto_profile(cls: type) -> type:
    """Decorate public instance methods with timing and optional profiling wrappers.

    The decorator preserves ``staticmethod`` and ``classmethod`` descriptors so that method
    bindings remain intact.
    """

    def make_wrapper(func: Callable[..., Any]) -> Callable[..., Any]:
        timed = func_time(func)
        profiled = func_time(func_cprofile(func))

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            enable_cprofile = getattr(builtins, "ENABLE_CPROFILE", False)
            if enable_cprofile:
                return profiled(*args, **kwargs)
            return timed(*args, **kwargs)

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
