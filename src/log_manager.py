"""
Log manager module.
"""
import logging
import logging.config
import os
from .utils import organize_files, get_filename

LOG_PATH = os.path.join(os.getcwd(), ".cache", "logs")

class LogManager:
    """Log manager singleton class."""
    __instance = None
    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance
    def __init__(self):
        self.logger = self._init_logger()
        organize_files(LOG_PATH, "LOG_")
    @staticmethod
    def _init_logger():
        """Initialize logger."""
        config = {
            'version': 1.0,
            'formatters': {
                'console_formatter': {
                    'format': '[%(asctime)s] [%(levelname)-10s]\t%(message)s',
                },
                'file_formatter': {
                    'format': (
                        '[%(asctime)s] [%(levelname)-10s] [%(filename)-20s] '
                        '[%(funcName)-20s] [%(lineno)-5d]\t%(message)s'
                    ),
                },
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
                },
            },
            'loggers': {
                'StreamLogger': {
                    'handlers': ['console'],
                    'level': 'DEBUG',
                },
                'FileLogger': {
                    'handlers': ['console', 'file'],
                    'level': 'DEBUG',
                },
            }
        }
        logging.config.dictConfig(config)
        return logging.getLogger("FileLogger")
    def get_logger(self):
        """Get logger instance."""
        return self.logger

log = LogManager().get_logger()
