'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 18:41:42
@LastEditTime: 2020-02-20 18:15:24
@LastEditors: WangGuanran
@Description: platform manager py ile
@FilePath: \vprojects\vprjcore\platform_manager.py
'''

import os
import sys
from functools import partial

from vprjcore.log import log

if __package__ is None:
    __package__ = "vprjcore"

get_full_path = partial(os.path.join, os.getcwd(), __package__, "platform")
PLATFORM_PLUGIN_PATH = get_full_path()


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
        self.name = __name__
        self._platform_info = {}
        self._loadPlugins()

    def _loadPlugins(self):
        for dirname in os.listdir(PLATFORM_PLUGIN_PATH):
            dirfullname = get_full_path(dirname)
            if os.path.isdir(dirfullname):
                for filename in os.listdir(dirfullname):
                    if not filename.endswith(".py") or filename.startswith("_"):
                        continue
                    self._runPlugin(dirname, filename)

    def _runPlugin(self, dirname, filename):
        pluginName = os.path.splitext(filename)[0]
        log.debug("pluginName = %s" % (pluginName))
        packageName = __package__ + ".platform."+dirname+'.'+pluginName
        log.debug("packageName = %s" % (packageName))
        plugin = __import__(packageName, fromlist=[pluginName])

        if hasattr(plugin, "get_platform"):
            platform = plugin.get_platform()
            platform.filename = plugin.__file__
            platform.pluginName = pluginName
            platform.vendor = dirname
            platform.packageName = packageName
            self.add_platform(platform)
        else:
            log.warning("file '%s' does not have 'get_platform',fail to register plugin" %
                        (plugin.__file__))

    def add_platform(self, platform):
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
                      (platform.pluginName, platform.support_list))
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

    def compatible(self, prj_info):
        log.debug("In!")
        try:
            return self._platform_info[prj_info["platform_name"].upper()]
        except:
            log.exception("Invalid platform '%s'" % (prj_info["platform"]))
            sys.exit(-1)


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
