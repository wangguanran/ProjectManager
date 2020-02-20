'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-15 22:10:25
@LastEditTime: 2020-02-21 00:15:34
@LastEditors: WangGuanran
@Description: analyse py file
@FilePath: \vprojects\vprjcore\analyse.py
'''

import cProfile
import os
import pstats
import time
import shutil
from functools import wraps

from vprjcore.common import _get_filename
from vprjcore.log import log


def func_time(func):

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(func.__name__, 'took', end - start, 'seconds')
        return result

    return wrapper


CPROFILE_PATH = "./.cache/cprofile/"

def organize_cprofile_files():
    if os.path.exists(CPROFILE_PATH):
        file_list = os.listdir(CPROFILE_PATH)
        for file in file_list:
            if os.path.isfile(CPROFILE_PATH + file):
                log_data = file.split("_")[1]
                log_dir = CPROFILE_PATH + "CPROFILE_"+log_data
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                shutil.move(CPROFILE_PATH+file, log_dir)

def func_cprofile(func):

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
                organize_cprofile_files()
                profile.dump_stats('profile_dump')  # Dump Binary File
                with open(_get_filename("Stats_", ".cprofile", CPROFILE_PATH), "w") as filesteam:
                    ps = pstats.Stats("profile_dump", stream=filesteam)
                    # ps.strip_dirs().sort_stats("time").print_stats()
                    ps.sort_stats("time").print_stats()
                    os.remove("profile_dump")
                # profile.print_stats(sort='time')
            except:
                os.remove("profile_dump")
                log.exception("fail to dump profile")

    return wrapper


try:
    from line_profiler import LineProfiler

    def func_line_time(follow=[]):

        def decorate(func):
            @wraps(func)
            def profiled_func(*args, **kwargs):
                try:
                    profiler = LineProfiler()
                    profiler.add_function(func)
                    for func in follow:
                        profiler.add_function(func)
                    profiler.enable_by_count()
                    return func(*args, **kwargs)
                finally:
                    profiler.print_stats()

            return profiled_func

        return decorate

except ImportError:
    # log.exception("Can not import line_profiler")

    def func_line_time(follow=[]):
        "Helpful if you accidentally leave in production!"
        def decorate(func):
            @wraps(func)
            def nothing(*args, **kwargs):
                return func(*args, **kwargs)

            return nothing

        return decorate


# def func_try_except(func):
#     """
#     save exception log
#     """

#     @wraps(func)
#     def wrapper(*args, **kwargs):
#         try:
#             return func(*args, **kwargs)
#         except:
#             log.exception("Something error!")

#     return wrapper
