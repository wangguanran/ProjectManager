'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-15 15:16:55
@LastEditTime: 2020-02-20 00:40:05
@LastEditors: WangGuanran
@Description: Log_Manager py File
@FilePath: \vprojects\vprjcore\log.py
'''

import os
import sys
import shutil
import logging
import logging.config

from vprjcore.common import _get_filename

LOG_PATH = "./.cache/logs/"


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
