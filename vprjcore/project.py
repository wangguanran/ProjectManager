'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-14 20:01:07
@LastEditTime: 2020-02-29 17:17:38
@LastEditors: WangGuanran
@Description: project_manager py file
@File_Path: /vprojects/vprjcore/project.py
'''

import os
import sys
import git
import json
import shutil
import datetime
import argparse
import threading
from collections import OrderedDict

from vprjcore.common import func_cprofile, log, get_full_path, list_file_path
from vprjcore.common import PLATFORM_ROOT_PATH, PROJECT_INFO_PATH, VPRJCORE_VERSION, VPRJCORE_PLUGIN_PATH


class Project(object):

    def __init__(self, args_dict: dict):
        operate = args_dict.pop("operate").lower()
        is_inner = args_dict.pop("is_inner")
        self.name = args_dict.pop("project_name").lower()
        self.is_board = args_dict.pop("is_board")
        self.base = args_dict.pop("base").lower()

        self.platform = self._get_platform_name(is_inner)
        op_handler = self._get_op_handler(is_inner)

        self.executed(operate, op_handler)

    @func_cprofile
    def executed(self, operate, op_handler):
        if operate in op_handler.keys():
            if op_handler[operate](self):
                self._update_platform_json_file()
                log.info("Operation succeeded!")
            else:
                log.info("Operation failed!")
        else:
            log.warning("Can not support this operate")

    def new_platform(self, *args, **kwargs):
        file_list = []
        link_list = {}
        platform_info = OrderedDict()

        if os.path.basename(os.getcwd()) in ["vprojects", "vprjcore"]:
            log.error("This command cannot be executed in the current directory")
            return False

        platform = self.platform
        platform_dir_path = get_full_path(platform)
        if not os.path.exists(platform_dir_path):
            os.makedirs(platform_dir_path)
        else:
            log.warning("The platform is already exists!")
            return False
        platform_info["platform"] = platform.upper()

        create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        platform_info["create_time"] = create_time

        log.debug("platform root path = %s" % PLATFORM_ROOT_PATH)
        for dirname in list_file_path(PLATFORM_ROOT_PATH, max_depth=1, only_dir=True):
            if os.path.basename(dirname) in ["vprojects", "zprojects"]:
                continue
            try:
                repo = git.Repo(dirname)
                untracked_files_list = repo.untracked_files
                if len(untracked_files_list) == 0:
                    continue
                for file_name in untracked_files_list:
                    src = os.path.join(
                        os.path.basename(dirname), file_name)
                    if os.path.islink(src):
                        soft_link_path = os.readlink(src)
                        log.debug("link='%s',file name='%s'" % (
                            soft_link_path, file_name))
                        link_list[src] = soft_link_path
                    else:
                        dest = os.path.join(
                            platform_dir_path, os.path.dirname(src))
                        log.debug("src='%s' dest='%s'" % (src, dest))
                        if not os.path.exists(dest):
                            os.makedirs(dest)
                        shutil.copy(src, dest)
                        file_list.append(src)
            except git.exc.InvalidGitRepositoryError:
                continue

        platform_info["link_list"] = link_list
        platform_info["file_list"] = file_list
        json_file_path = get_full_path(platform, platform+".json")
        with open(json_file_path, "w+") as f_write:
            json.dump(platform_info, f_write, indent=4)

        return True

    def _get_platform_name(self, is_inner):
        platform = None

        if is_inner:
            return self.name
        else:
            try:
                json_info = json.load(open(PROJECT_INFO_PATH, "r"))
                if self.name in json_info.keys():
                    platform = json_info[self.name]["platform"]
                elif self.base in json_info.keys():
                    platform = json_info[self.base]["platform"]
                else:
                    log.debug("Can not find the project's platform")
            except FileNotFoundError:
                log.exception("'%s' does not exists" % PROJECT_INFO_PATH)

        return platform

    def _update_platform_json_file(self):
        prj_info = OrderedDict()
        prj_info_temp = OrderedDict()
        json_info = OrderedDict()
        try:
            prj_info_temp = json.load(open(PROJECT_INFO_PATH, "r"))
        except:
            log.debug("%s is null" % PROJECT_INFO_PATH)

        prj_info["platform"] = self.platform.upper()
        platform_info["create_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        platform_info["base"] = self.base
        platform_info["status"] = "normal"

        prj_info_temp[self.name] = prj_info
        prj_list = sorted(prj_info_temp.keys())
        for info in prj_list:
            json_info[info] = prj_info_temp[info]
        json.dump(json_info, open(PROJECT_INFO_PATH, "w+"), indent=4)

        return True

    def _get_op_handler(self, is_inner):
        op_handler = {}
        module = None

        if self.platform is None:
            log.error("The platform is None,please check the project's name")
            return None

        if is_inner:
            module = self
        else:
            # Scan module info
            for dir_path in list_file_path(VPRJCORE_PLUGIN_PATH, only_dir=True):
                for file_path in list_file_path(dir_path):
                    if not file_path.endswith(".py"):
                        continue
                    log.debug("file_path=%s" % file_path)
                    name = os.path.basename(file_path).split(sep=".")[0]
                    start_index = file_path.find("vprjcore")
                    end_index = file_path.find(".py")
                    package = file_path[start_index:end_index].replace(
                        os.sep, ".")
                    log.debug("name=%s,package=%s" % (name, package))
                    import_module = __import__(package, fromlist=[name])
                    if hasattr(import_module, "get_platform"):
                        temp = import_module.get_platform()
                        if hasattr(temp, "support_list"):
                            if self.platform in temp.support_list:
                                module = temp
                                break

        if module:
            for attr in dir(module):
                if attr.startswith("_"):
                    continue
                funcattrs = getattr(module, attr)
                if callable(funcattrs):
                    op_handler[attr] = funcattrs
            return op_handler
        else:
            return None


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
    parser.add_argument("project_name", help="project name")

    parser.add_argument('-b', action="store_true", dest="is_board",
                        help="specify the new project as the board project", default=False)
    parser.add_argument(
        "--base", help="specify a new project to be created based on this", default="None")

    parser.add_argument('-i', action="store_true", dest="is_inner",
                        help="specify this operation as an internal instruction", default=False)

    args = parser.parse_args()
    # log.info(args.__dict__)
    return args.__dict__


if __name__ == "__main__":
    args_dict = parse_cmd()
    project = Project(args_dict)
