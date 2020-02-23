'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 00:35:02
@LastEditTime: 2020-02-23 15:35:47
@LastEditors: WangGuanran
@Description: common py file
@FilePath: \vprojects\vprjcore\common.py
'''
import cProfile
import logging
import logging.config
import os
import pstats
import shutil
import time
from functools import partial, wraps

if os.path.basename(os.getcwd()) == "vprojects":
    get_full_path = partial(os.path.join, os.getcwd())
elif os.path.basename(os.getcwd()) in ["vprjcore","scripts"]:
    get_full_path = partial(os.path.join, os.path.dirname(os.getcwd()))
else:
    get_full_path = partial(os.path.join, os.getcwd(), "vprojects")

VPRJCORE_VERSION = "0.0.1"
LOG_PATH = get_full_path(".cache", "logs")
CPROFILE_PATH = get_full_path(".cache", "cprofile")
PROFILE_DUMP_NAME = "profile_dump"


def dependency(depend_list):
    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # log.debug("depend list = %s"%(depend_list))
            project = args[1]
            for depend_one in depend_list:
                # print(depend_list)
                for plugin in project.plugin_list:
                    # print(plugin.module_name)
                    if plugin.module_name == depend_one:
                        # depend_func = getattr(plugin,func.__name__)
                        # depend_func(project)
                        index, operate = func.__name__.split(
                            sep="_", maxsplit=1)
                        if operate in plugin.operate_list:
                            if index in plugin.operate_list[operate]:
                                plugin.operate_list[operate][index](project)
                                del plugin.operate_list[operate][index]
                            else:
                                log.warning(
                                    "The plugin does not have the attr:'%s'" % func.__name__)
                        else:
                            log.warning(
                                "The plugin does not have the attr:'%s'" % func.__name__)

            return func(*args, **kwargs)

        return wrapper

    return decorate


def get_filename(prefix, suffix, path):
    """
    return file name based on time
    """
    path = get_full_path(path)
    if not os.path.exists(path):
        os.makedirs(path)
    date_str = time.strftime('%Y%m%d_%H%M%S')
    return os.path.join(path, ''.join((prefix, date_str, suffix)))


def organize_files(path, prefix):
    # print("prefix = %s,path = %s" % (prefix, path))
    if os.path.exists(path):
        file_list = os.listdir(path)
        for file in file_list:
            file_fullpath = get_full_path(path, file)
            if os.path.isfile(file_fullpath):
                log_data = file.split("_")[1]
                log_dir = get_full_path(path, prefix + log_data)
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                shutil.move(file_fullpath, log_dir)


###############################################################
#
#       For Load Module
#
###############################################################


def list_file_path(module_path, max_depth=0xff, cur_depth=0, list_dir=False, only_dir=False):
    cur_depth += 1
    module_path = get_full_path(module_path)
    # log.debug("module_path = %s,max_depth = %d,cur_depth = %d"%(module_path,max_depth,cur_depth))
    for filename in os.listdir(module_path):
        filename = get_full_path(module_path, filename)
        if os.path.isdir(filename):
            # log.debug("cur_depth = %d,isdir = %s"%(cur_depth,filename))
            if cur_depth < max_depth:
                for subdir_filename in list_file_path(filename, max_depth, cur_depth, list_dir, only_dir):
                    yield subdir_filename
            if list_dir or only_dir:
                yield filename
        elif not only_dir:
            yield filename


def load_module(module_path, max_depth):
    # log.debug(module_path)
    module_list = []

    module_path = get_full_path(module_path)
    log.debug("module path = '%s'" % module_path)
    if not os.path.exists(module_path):
        log.warning("the module_path '%s' is not exits" % module_path)
        return None

    for filepath in list_file_path(module_path, max_depth):
        # log.debug(file_path)
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
            module.file_path = import_module.__file__
            module.module_name = module_name
            module.package_name = package_name
            if register_module(module):
                module_list.append(module)
    return module_list


def register_module(module):
    module.operate_list = {}

    attrlist = dir(module)
    for attr in attrlist:
        if not attr.startswith("_"):
            funcattrs = getattr(module, attr)
            if callable(funcattrs):
                # for before_new_project -> before new_project
                if attr.count("_") > 1:
                    index, operate = attr.split(sep="_", maxsplit=1)
                    if operate not in module.operate_list.keys():
                        module.operate_list[operate] = {}
                    module.operate_list[operate][index] = funcattrs
                # for new_project
                else:
                    module.operate_list[attr] = funcattrs
    if module.operate_list:
        log.debug("module module_name = %s" % module.module_name)
        log.debug("module package_name = %s" % module.package_name)
        log.debug("module file_path = '%s'" % module.file_path)
        log.debug("module operate_list = %s" % module.operate_list)
        log.debug("register '%s' successfully!" % module.module_name)
        return True
    else:
        log.warning("No matching function in '%s'" % module.module_name)
        return False


###############################################################
#
#       LogManager  ：  For Logging System
#
###############################################################


class LogManager(object):
    """
    Singleton mode
    """
    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self):
        # Initialize logger object
        self.logger = self._init_logger()
        # Organize log files
        organize_files(LOG_PATH, "LOG_")

    @staticmethod
    def _init_logger():
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
                    'level': 'INFO',
                    'formatter': 'console_formatter'
                },
                'file': {
                    'class': 'logging.FileHandler',
                    'filename': get_filename("Log_", ".log", LOG_PATH),
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

    def get_logger(self):
        return self.logger


log = LogManager().get_logger()


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
                organize_files(CPROFILE_PATH, "CPROFILE_")
                profile.dump_stats(PROFILE_DUMP_NAME)  # Dump Binary File
                with open(get_filename("Stats_", ".cprofile", CPROFILE_PATH), "w") as file_steam:
                    ps = pstats.Stats(PROFILE_DUMP_NAME, stream=file_steam)
                    # ps.strip_dirs().sort_stats("time").print_stats()
                    ps.sort_stats("time").print_stats()
                    if os.path.exists(PROFILE_DUMP_NAME):
                        os.remove(PROFILE_DUMP_NAME)
                # profile.print_stats(sort='time')
            except:
                if os.path.exists(PROFILE_DUMP_NAME):
                    os.remove(PROFILE_DUMP_NAME)
                log.exception("fail to dump profile")

    return wrapper

#
# try:
#     from line_profiler import LineProfiler
#
#
#     def func_line_time(follow=None):
#
#         if follow is None:
#             follow = []
#
#         def decorate(func):
#             @wraps(func)
#             def profiled_func(*args, **kwargs):
#                 try:
#                     profiler = LineProfiler()
#                     profiler.add_function(func)
#                     for func in follow:
#                         profiler.add_function(func)
#                     profiler.enable_by_count()
#                     return func(*args, **kwargs)
#                 finally:
#                     profiler.print_stats()
#
#             return profiled_func
#
#         return decorate
#
# except ImportError:
#     # log.exception("Can not import line_profiler")
#
#     def func_line_time(follow=[]):
#         "Helpful if you accidentally leave in production!"
#
#         def decorate(func):
#             @wraps(func)
#             def nothing(*args, **kwargs):
#                 return func(*args, **kwargs)
#
#             return nothing
#
#         return decorate

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
