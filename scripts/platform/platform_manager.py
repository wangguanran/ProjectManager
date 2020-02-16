'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 18:41:42
@LastEditTime: 2020-02-16 18:41:42
@LastEditors: WangGuanran
@Description: platform manager py ile
@FilePath: \vprojects\scripts\platform_manager.py
'''

import os
from functools import partial

from scripts.log import log
from scripts.common import global_info

support_operate = global_info['support_operate']

# PLATFORM_FILE_PATH = "scripts/platform/"
get_full_path = partial(os.path.join, os.getcwd(), "scripts", "platform")
PLATFORM_PLUGIN_PATH = get_full_path()


class PlatformManager(object):

    def __init__(self):
        self.name = __name__
        self._platform_info = {}
        self._loadPlugins()

    def _loadPlugins(self):
        # log.debug(os.listdir(PLATFORM_PLUGIN_PATH))
        for dirname in os.listdir(PLATFORM_PLUGIN_PATH):
            dirfullname = get_full_path(dirname)
            if os.path.isdir(dirfullname):
                # log.debug(os.listdir(dirfullname))
                for filename in os.listdir(dirfullname):
                    if not filename.endswith(".py") or filename.startswith("_"):
                        continue
                    self._runPlugin(dirname, filename)

    def _runPlugin(self, dirname, filename):
        pluginName = os.path.splitext(filename)[0]
        log.debug("pluginName = %s" % (pluginName))
        packageName = "scripts.platform."+dirname+'.'+pluginName
        log.debug("packageName = %s" % (packageName))
        plugin = __import__(packageName, fromlist=[pluginName])
        # Errors may be occured. Handle it yourself.
        plugin.register_platform(self)

    def add_platform(self, platform):
        attr = dir(platform)
        log.debug(attr)
        support_count = 0
        for op, func in support_operate.items():
            if not func in attr:
                log.warning("Missing attributes = %s "%(func))
            else:
                support_count += 1
        if support_count == len(support_operate):
            if "support_list" in attr:
                log.debug("Add platform (%s)"%(platform.support_list))
                for data in platform.support_list:
                    log.debug("platform '%s' register successfully!"%(data))
                    self._platform_info[data] = platform
            else:
                log.warning("%s object has no attribute 'support_list'",platform.__class__)
        else:
            log.warning("platform is invalid!")

    def compatible(self, prj_info):
        log.debug("In!")
        return self._platform_info[prj_info["platform"]]


if __name__ == "__main__":
    platform = PlatformManager()
