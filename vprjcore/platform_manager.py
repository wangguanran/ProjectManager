'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 18:41:42
@LastEditTime: 2020-02-22 10:44:15
@LastEditors: WangGuanran
@Description: platform manager py ile
@FilePath: \vprojects\vprjcore\platform_manager.py
'''

import os
import sys

from vprjcore.common import log, get_full_path, load_module

PLATFORM_PLUGIN_PATH = get_full_path("vprjcore", "platform")


class PlatformManager(object):

    '''
    Singleton mode
    '''
    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self):
        self.platform_list = load_module(PLATFORM_PLUGIN_PATH, 2)

    def before_new_project(self, project):
        platform_name = project.args_dict["base"]
        log.debug("platform name = %s"%(platform_name))

        for platform in self.platform_list:
            for name in platform.support_list:
                if(platform_name.upper() == name.upper()):
                    project.platform_handler = platform.operate_list
                    return True


    def before_compile_project(self):
        pass


def get_module():
    return PlatformManager()


if __name__ == "__main__":
    platform = PlatformManager()

'''
from vprjcore.log import log

class Platform(object):

    def __init__(self):
        self.support_list = [
            "MT6735",
            "MT6739",
        ]

    def new_project(self, *args, **kwargs):
        log.debug("In!")
        log.debug(args[0])

    def del_project(self, *args, **kwargs):
        log.debug("In!")

    def compile_project(self, *args, **kwargs):
        log.debug("In!")


# All platform scripts must contain this interface
def get_platform():
    return Platform()
'''
