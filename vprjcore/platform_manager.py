'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 18:41:42
@LastEditTime: 2020-02-24 23:50:02
@LastEditors: WangGuanran
@Description: platform manager py ile
@FilePath: /vprojects/vprjcore/platform_manager.py
'''
import os
import sys
import argparse
import git
import shutil
import json
import datetime

from vprjcore.common import log, get_full_path, load_module, dependency, VPRJCORE_VERSION, list_file_path, func_cprofile

PLATFORM_PLUGIN_PATH = get_full_path("vprjcore", "custom")
PLATFORM_ROOT_PATH = os.path.dirname(get_full_path())


class PlatformManager(object):

    """
    Singleton mode
    """
    __instance = None

    def __new__(cls, *args, **kwargs):
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
            log.info("'%s' down! result = %s" %
                     (self.operate, self._dispatch()))

    @func_cprofile
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
        except_list = [
            "out", ".repo", "vprojects", "zprojects", "build"
        ]
        json_info = {}
        file_list = []
        link_list = {}
        platform_info = {}

        if os.path.basename(os.getcwd()) in ["vprojects", "vprjcore"]:
            log.error("This command cannot be executed in the current directory")
            return False

        platform_name = input("Please input the platform name:")
        log.debug("platform name = %s" % platform_name)

        create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.debug("create time = %s" % create_time)
        platform_info["create_time"] = create_time

        platform_dir_path = get_full_path("new_project_base", platform_name)
        if not os.path.exists(platform_dir_path):
            os.makedirs(platform_dir_path)
        json_file_path = os.path.join(
            platform_dir_path, platform_name+"_config_info.json")

        for dirname in list_file_path(PLATFORM_ROOT_PATH, max_depth=1, only_dir=True):
            if os.path.basename(dirname) not in except_list:
                try:
                    repo = git.Repo(dirname)
                    untracked_files_list = repo.untracked_files
                    if len(untracked_files_list) > 0:
                        for file_name in untracked_files_list:
                            full_path = os.path.join(
                                os.path.basename(dirname), file_name)
                            if os.path.islink(full_path):
                                soft_link_path = os.readlink(full_path)
                                log.debug("soft link path = %s,file name = %s" % (
                                    soft_link_path, file_name))
                                link_list[full_path] = soft_link_path
                            else:
                                file_list.append(full_path)
                                log.debug("normal file = %s" % full_path)
                                dest_dir_path = os.path.join(
                                    platform_dir_path, os.path.dirname(full_path))
                                log.debug("dest dir path = %s" % dest_dir_path)
                                if not os.path.exists(dest_dir_path):
                                    os.makedirs(dest_dir_path)
                                shutil.copy(full_path, dest_dir_path)
                except git.exc.InvalidGitRepositoryError:
                    continue

        platform_info["file_list"] = file_list
        platform_info["link_list"] = link_list
        json_info[platform_name] = platform_info
        with open(json_file_path, "w+") as f_write:
            json.dump(json_info, f_write, indent=4, sort_keys=True)
        return True

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
