"""
Profiling decorators for performance analysis.
"""
import time
import cProfile
import pstats
import os
from functools import wraps
from src.log_manager import log
from src.utils import path_from_root, get_filename, organize_files

CPROFILE_PATH = path_from_root(".cache", "cprofile")
PROFILE_DUMP_NAME = "profile_dump"

def func_time(func):
    """Decorator to measure function execution time."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(func.__name__, 'took', end - start, 'seconds')
        return result
    return wrapper

def func_cprofile(func):
    """Decorator to profile a function using cProfile and dump stats."""
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
                organize_files(CPROFILE_PATH, "CPROFILE_")
                profile.dump_stats(PROFILE_DUMP_NAME)
                stats_path = get_filename(
                    "Stats_", ".cprofile", CPROFILE_PATH)
                with open(stats_path, "w", encoding="utf-8") as file_steam:
                    ps = pstats.Stats(PROFILE_DUMP_NAME, stream=file_steam)
                    ps.sort_stats("time").print_stats()
                    if os.path.exists(PROFILE_DUMP_NAME):
                        os.remove(PROFILE_DUMP_NAME)
            except OSError:
                if os.path.exists(PROFILE_DUMP_NAME):
                    os.remove(PROFILE_DUMP_NAME)
                log.exception("fail to dump profile")
    return wrapper
