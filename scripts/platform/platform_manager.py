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

from scripts.log import log

class PlatformManager(object):

    def __init__(self):
        self._loadPlugins()

    def _loadPlugins(self):
        log.debug(os.listdir("."))
        for filename in os.listdir("."):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
            self.runPlugin(filename)

    def runPlugin(self, filename):
        pluginName=os.path.splitext(filename)[0]
        plugin=__import__("plugins."+pluginName, fromlist=[pluginName])
        #Errors may be occured. Handle it yourself.
        plugin.run(self)

if __name__=="__main__":
    platform=PlatformManager()