'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 18:41:42
@LastEditTime: 2020-02-23 15:58:33
@LastEditors: WangGuanran
@Description: platform manager py ile
@FilePath: \vprojects\vprjcore\platform_manager.py
'''
import os
import sys
import argparse
from git import Repo

from vprjcore.common import log, get_full_path, load_module, dependency, VPRJCORE_VERSION, list_file_path

PLATFORM_PLUGIN_PATH = get_full_path("vprjcore", "platform")
PLATFORM_ROOT_PATH = os.path.dirname(get_full_path())

class PlatformManager(object):

    """
    Singleton mode
    """
    __instance = None

    def __new__(cls,*args,**kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, args_dict=None):
        self.platform_list = load_module(PLATFORM_PLUGIN_PATH, max_depth=2)
        if not args_dict is None:
            self.operate = args_dict.pop("operate")
            self.args_dict = args_dict
            log.debug("operate = %s,args_dict = %s" %
                      (self.operate, self.args_dict))
            self._dispatch()

    def _dispatch(self):
        func_name = "_" + self.operate
        log.debug("func name = %s" % func_name)
        func_attr = getattr(self, func_name)
        if func_attr is None:
            log.error("the operate is not support")
            return False
        else:
            return func_attr()

    def _add_new_platform(self):
        log.debug("In")
        log.debug("platform root path = %s" % PLATFORM_ROOT_PATH)
        for dirname in list_file_path(PLATFORM_ROOT_PATH,only_dir=True):
            repo = Repo(dirname)
            print(repo.git.status())


    @dependency(["project_manager"])
    def before_new_project(self, project):
        platform_name = project.platform_name
        log.debug("platform name = %s" % platform_name)

        for platform in self.platform_list:
            for name in platform.support_list:
                if platform_name.upper() == name.upper():
                    project.platform_handler = platform.operate_list
                    return True

        return False

    def before_compile_project(self):
        pass


def get_module():
    return PlatformManager()


def parse_cmd():
    """
    @description: Parsing command line parameters
    @param {type} None
    @return: arg list(dict)
    """
    log.debug("argv = %s" % sys.argv)
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', action="version",
                        version=VPRJCORE_VERSION)
    parser.add_argument("operate", help="supported operations")

    args = parser.parse_args()
    log.info(args.__dict__)
    return args.__dict__

if __name__ == "__main__":
    args_dict = parse_cmd()
    platform = PlatformManager(args_dict)

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
