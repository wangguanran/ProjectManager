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

from scripts.common import _get_filename

LOG_PATH = "./.cache/logs/"


class LogManager(object):

    def __init__(self):
        self.logger = self._init_logger()

    def _init_logger(self):
        config = {
            'version': 1.0,
            'formatters': {
                'console_formatter': {
                    'format': '[%(asctime)s]\t%(message)s',
                },
                'file_formatter': {
                    'format': '[%(asctime)s] [%(levelname)-10s] [%(filename)-20s] [%(funcName)-20s] [%(lineno)-5d]\t%(message)s',
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
                    'filename': _get_filename("Log_", ".log", LOG_PATH),
                    'level': 'DEBUG',
                    'mode': 'w',
                    'formatter': 'file_formatter',
                    'encoding': 'utf8',
                    'delay':'True',
                },
                'file_base_time': {
                    'class': 'logging.handlers.TimedRotatingFileHandler',
                    'filename': 'Log.log',
                    'level': 'DEBUG',
                    'formatter': 'file_formatter',
                    'encoding': 'utf8',
                    'delay':'True',
                    # 'interval':1,
                    # 'when': 'S',
                    # 'backupCount': 10,
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

    def getLogger(self):
        return self.logger


if __name__ == "__main__":
    pass
else:
    log = LogManager().getLogger()
