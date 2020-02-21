'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 00:35:02
@LastEditTime: 2020-02-21 17:50:08
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
from functools import partial

get_full_path = partial(os.path.join, os.getcwd())
LOG_PATH = "./.cache/logs/"


def _get_filename(preffix, suffix, path):
    '''
    return file name based on time
    '''
    if(not os.path.exists(path)):
        os.makedirs(path)
    date_str = time.strftime('%Y%m%d_%H%M%S')
    return os.path.join(path, ''.join((preffix, date_str, suffix)))


class LogManager(object):

    def __init__(self):
        # Initialize logger object
        self.logger = self._init_logger()
        # Organize log files
        self.organize_log_files()

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

    def organize_log_files(self):
        if os.path.exists(LOG_PATH):
            file_list = os.listdir(LOG_PATH)
            for file in file_list:
                if os.path.isfile(LOG_PATH + file):
                    log_data = file.split("_")[1]
                    log_dir = LOG_PATH + "LOG_"+log_data
                    if not os.path.exists(log_dir):
                        os.makedirs(log_dir)
                    shutil.move(LOG_PATH+file, log_dir)


log = LogManager().getLogger()


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


def load_module(caller,module_path, max_depth):
    module_path = get_full_path(module_path)
    for filepath in list_file_path(module_path, max_depth):
        log.debug(filepath)
        filename = os.path.basename(filepath)
        if not filename.endswith(".py") or filename.startswith("_"):
            continue

        module_name = os.path.splitext(filename)[0]
        start_index = filepath.find("vprjcore")
        end_index = filepath.find(".py")
        packageName = filepath[start_index:end_index].replace(os.sep,".")
        log.debug("packageName = %s" % (packageName))
        import_module = __import__(packageName, fromlist=[module_name])

        if hasattr(import_module, "get_module"):
            module = import_module.get_module()
            module.filename = import_module.__file__
            module.module_name = module_name
            module.packageName = packageName
            register_module(caller,module)
        else:
            log.warning("file '%s' does not have 'get_module',fail to register module" %
                        (import_module.__file__))

def register_module(caller,module):
    caller.module_info = {}
    module.operate_list = {}

    attrlist = dir(module)
    for attr in attrlist:
        if not attr.startswith("_"):
            funcaddr = getattr(module, attr)
            if callable(funcaddr):
                if "_" in attr:
                    index, operate = attr.split(sep="_",maxsplit=1)
                    if not operate in module.operate_list.keys():
                        module.operate_list[operate] = {}
                    module.operate_list[operate][index] = funcaddr
    log.debug(module.operate_list)
    if module.operate_list:
        log.debug("register '%s' successfully!" % (module.module_name))
        caller.module_info[module.module_name] = module
    else:
        log.warning("No matching function in '%s'" % (module.module_name))
