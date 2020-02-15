'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-15 15:16:55
@LastEditTime: 2020-02-15 21:50:43
@LastEditors: WangGuanran
@Description: Log_Manager py File
@FilePath: \vprojects\scripts\log.py
'''

import logging
import logging.config
import os
import platform
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

LOG_PATH = "./.cache/logs/"


class Log_Manager(object):

    def __init__(self):
        self._check_logpath()
        self.log = self._init_logger()

    def _get_filename(self, preffix="Log", suffix=".log", logpath=LOG_PATH):
        date_str = time.strftime('%Y%m%d_%H%M%S')
        return os.path.join(logpath, ''.join((preffix, date_str, suffix)))

    def _init_logger(self):
        config = {
            'version': 1,
            'formatters': {
                'console_formatter': {
                    'format': '[%(asctime)s] [%(levelname)-10s]\t%(message)s',
                },
                'file_formatter': {
                    'format': '[%(asctime)s] [%(levelname)-10s] [%(filename)-20s] [%(funcName)-10s] [%(lineno)-5d]\t%(message)s',
                },
                # 其他的 formatter
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'level': 'INFO',
                    'formatter': 'console_formatter'
                },
                'file': {
                    'class': 'logging.FileHandler',
                    'filename': self._get_filename(),
                    'level': 'DEBUG',
                    'mode': 'w',
                    'formatter': 'file_formatter',
                    'encoding': 'utf8',
                },
                'file_base_time': {
                    'class': 'logging.handlers.TimedRotatingFileHandler',
                    'filename': 'Log.log',
                    'level': 'DEBUG',
                    'formatter': 'file_formatter',
                    'encoding': 'utf8',
                    # 'interval':1,
                    'when': 'S',
                    'backupCount': 10,
                },
                # 其他的 handler
            },
            'loggers': {
                'StreamLogger': {
                    'handlers': ['console'],
                    'level': 'DEBUG',
                },
                'FileLogger': {
                    # 既有 console Handler，还有 file Handler
                    'handlers': ['console', 'file'],
                    'level': 'DEBUG',
                },
                # 其他的 Logger
            }
        }
        logging.config.dictConfig(config)
        return logging.getLogger("FileLogger")

    def _check_logpath(self, logpath=LOG_PATH):
        if(not os.path.exists(logpath)):
            os.makedirs(logpath)

    def getLogger(self):
        return self.log


if __name__ == "__main__":
    pass
else:
    log = Log_Manager().getLogger()
