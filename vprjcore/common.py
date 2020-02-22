'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 00:35:02
@LastEditTime: 2020-02-22 09:33:05
@LastEditors: WangGuanran
@Description: common py file
@FilePath: \vprojects\vprjcore\common.py
'''
import os
import time
import sys
import shutil
import logging
import logging.config
import cProfile
from functools import partial, wraps

get_full_path = partial(os.path.join, os.getcwd())
LOG_PATH = get_full_path(".cache", "logs")


def _get_filename(preffix, suffix, path):
    '''
    return file name based on time
    '''
    if(not os.path.exists(path)):
        os.makedirs(path)
    date_str = time.strftime('%Y%m%d_%H%M%S')
    return os.path.join(path, ''.join((preffix, date_str, suffix)))


def organize_log_files(path, preffix):
    if os.path.exists(path):
        file_list = os.listdir(path)
        for file in file_list:
            file_fullpath = get_full_path(path, file)
            if os.path.isfile(file_fullpath):
                log_data = file.split("_")[1]
                log_dir = get_full_path(path, preffix + log_data)
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                shutil.move(file_fullpath, log_dir)

###############################################################
#
#       For Load Module
#
###############################################################

def list_file_path(module_path, max_depth, cur_depth=0):
    cur_depth += 1
    # log.debug("module_path = %s,max_depth = %d,cur_depth = %d"%(module_path,max_depth,cur_depth))
    for filename in os.listdir(module_path):
        filename = get_full_path(module_path, filename)
        if os.path.isdir(filename):
            # log.debug("cur_depth = %d,isdir = %s"%(cur_depth,filename))
            if(cur_depth < max_depth):
                for subdir_filename in list_file_path(filename, max_depth, cur_depth):
                    yield subdir_filename
        else:
            yield filename

def load_module(caller, module_path, max_depth):
    # log.debug(module_path)
    module_path = get_full_path(module_path)
    for filepath in list_file_path(module_path, max_depth):
        # log.debug(filepath)
        filename = os.path.basename(filepath)
        if not filename.endswith(".py") or filename.startswith("_"):
            continue

        module_name = os.path.splitext(filename)[0]
        start_index = filepath.find("vprjcore")
        end_index = filepath.find(".py")
        package_name = filepath[start_index:end_index].replace(os.sep, ".")
        import_module = __import__(package_name, fromlist=[module_name])

        if hasattr(import_module, "get_module"):
            module = import_module.get_module()
            module.filename = import_module.__file__
            module.module_name = module_name
            module.package_name = package_name
            register_module(caller, module)
        else:
            if hasattr(caller, "unload_list"):
                if not os.path.basename(filepath) in caller.unload_list:
                    log.warning("file '%s' does not have 'get_module',fail to register module" %
                                (import_module.__file__))

def register_module(caller, module):
    caller.module_info = {}
    module.operate_list = {}

    attrlist = dir(module)
    for attr in attrlist:
        if not attr.startswith("_"):
            funcaddr = getattr(module, attr)
            if callable(funcaddr):
                # for before_new_project -> before new_project
                if attr.count("_") > 1:
                    index, operate = attr.split(sep="_", maxsplit=1)
                    if not operate in module.operate_list.keys():
                        module.operate_list[operate] = {}
                    module.operate_list[operate][index] = funcaddr
                # for new_project
                else:
                    module.operate_list[attr] = funcaddr
    # log.debug(module.operate_list)
    if module.operate_list:
        log.debug("module filename = %s"%(module.module_name))
        log.debug("module packagename = %s"%(module.package_name))
        log.debug("module filename = %s"%(module.filename))
        log.debug("module operate_list = %s"%(module.operate_list))
        caller.module_info[module.module_name] = module
        log.debug("register '%s' successfully!" % (module.module_name))
    else:
        log.warning("No matching function in '%s'" % (module.module_name))

###############################################################
#
#       LogManager  ：  For Logging System
#
###############################################################
class LogManager(object):

    '''
    Singleton mode
    '''
    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self):
        # Initialize logger object
        self.logger = self._init_logger()
        # Organize log files
        organize_log_files(LOG_PATH, "LOG_")

    def _init_logger(self):
        config = {
            'version': 1.0,
            'formatters': {
                'console_formatter': {
                    'format': '[%(asctime)s] [%(levelname)-10s]\t%(message)s',
                },
                'file_formatter': {
                    'format': '[%(asctime)s] [%(levelname)-10s] [%(filename)-20s] [%(funcName)-20s] [%(lineno)-5d]\t%(message)s',
                },
                # other formatter
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'level': 'WARNING',
                    'formatter': 'console_formatter'
                },
                'file': {
                    'class': 'logging.FileHandler',
                    'filename': _get_filename("Log_", ".log", LOG_PATH),
                    'level': 'DEBUG',
                    'mode': 'w',
                    'formatter': 'file_formatter',
                    'encoding': 'utf8',
                    'delay': 'True',
                },
                'file_base_time': {
                    'class': 'logging.handlers.TimedRotatingFileHandler',
                    'filename': 'Log.log',
                    'level': 'DEBUG',
                    'formatter': 'file_formatter',
                    'encoding': 'utf8',
                    'delay': 'True',
                    # 'interval':1,
                    # 'when': 'S',
                    # 'backupCount': 10,
                },
                # other handler
            },
            'loggers': {
                'StreamLogger': {
                    'handlers': ['console'],
                    'level': 'DEBUG',
                },
                'FileLogger': {
                    # both 'console Handler' and 'file Handler'
                    'handlers': ['console', 'file'],
                    'level': 'DEBUG',
                },
                # other Logger
            }
        }
        logging.config.dictConfig(config)
        return logging.getLogger("FileLogger")

    def getLogger(self):
        return self.logger


log = LogManager().getLogger()

###############################################################
#
#       For Performance analysis
#
###############################################################


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
                organize_cprofile_files(CPROFILE_PATH, "CPROFILE_")
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
