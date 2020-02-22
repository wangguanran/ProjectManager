'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 18:41:42
@LastEditTime: 2020-02-22 09:35:25
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
        self._platform_info = {}
        self.is_need_split = False
        # self._loadPlugins()
        load_module(self, PLATFORM_PLUGIN_PATH, 2)
        # self._add_platform()

    def before_all_command(self,project):
        log.debug("In!")

    def _add_platform(self,platform):
        attrlist = dir(platform)
        log.debug(attrlist)

        platform.op_handler = {}
        for attr in attrlist:
            if not attr.startswith("_"):
                funcaddr = getattr(platform, attr)
                if callable(funcaddr):
                    platform.op_handler[attr] = funcaddr
        log.debug(platform.op_handler)

        if "support_list" in attrlist:
            log.debug("%s support list (%s)" %
                      (platform.module_name, platform.support_list))
            for data in platform.support_list:
                # Case insensitive
                data = data.upper()
                if data in self._platform_info:
                    log.warning(
                        "The platform '%s' is already registered by %s,%s register failed" % (data, self._platform_info[data].filename, platform.filename))
                else:
                    log.info(
                        "platform '%s' register successfully!" % (data))
                    self._platform_info[data] = platform
        else:
            log.warning(
                "%s object has no attribute 'support_list'", platform.__class__)

    def _compatible(self, platform_name):
        log.debug("In!")
        platform_name = platform_name.upper()
        try:
            return self._platform_info[platform_name].op_handler
        except:
            log.exception("Invalid platform '%s'" % (platform_name))
            sys.exit(-1)


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
