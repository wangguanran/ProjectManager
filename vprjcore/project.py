'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-14 20:01:07
@LastEditTime: 2020-02-29 10:32:09
@LastEditors: WangGuanran
@Description: project_manager py file
@File_Path: /vprojects/vprjcore/project.py
'''

import os
import sys
import json
import argparse

from vprjcore.project_manager import ProjectManager
from vprjcore.platform_manager import PlatformManager
from vprjcore.common import func_cprofile, log, get_full_path,PROJECT_INFO_PATH, VPRJCORE_VERSION, list_file_path


class Project(object):

    def __init__(self, args_dict: dict, auto_dispatch=True):
        self.operate = args_dict.pop("operate").lower()
        self.name = args_dict.pop("project_name").lower()
        self.is_board = args_dict.pop("is_board", False)
        self.base = args_dict.pop("base", None)

        self.platform = get_platform_name(self)
        self.platform_handler = get_platform_handler(self)

        # if auto_dispatch:
        #     log.info("%s '%s' down! Result = %s" %
        #              (self.operate, self.project_name, self.dispatch()))

    @func_cprofile
    def dispatch(self):
        """
        @description: Distribute operations to platform interface
        @param {type} None
        @return: None
        """
        try:
            if self._before_operate():
                log.debug("before operate down...")
                if self.platform_handler[self.operate](self):
                    log.debug("platform handler down...")
                    if self._after_operate():
                        log.debug("after operate down...")
                        return True
                    else:
                        log.debug("after operate failed!")
                else:
                    log.debug("platform handler failed!")
            else:
                log.debug("before operate failed!")

            return False
        except:
            log.exception("Error occurred!")
            return False

    def _polling_plugin_list_and_execute(self, exec_pos):
        """
        @description: Poll to check if the plug-in list has operations
                        at the location specified by exec_pos
        @param {type} exec_pos:execution position
        @return: None
        """
        for plugin in self.plugin_list:
            if self.operate in plugin.operate_list:
                if exec_pos in plugin.operate_list[self.operate]:
                    if plugin.operate_list[self.operate][exec_pos](self):
                        del plugin.operate_list[self.operate][exec_pos]
                    else:
                        log.debug("plugin '%s' operate failed!" %
                                  plugin.module_name)
                        return False

        return True

    def _before_operate(self):
        """
        @description: Perform operation in 'before' position
        @param {type} None
        @return: None
        """
        return self._polling_plugin_list_and_execute("before")

    def _after_operate(self):
        """
        @description: Perform operation in 'after' position
        @param {type} None
        @return: None
        """
        return self._polling_plugin_list_and_execute("after")


def get_platform_name(p: Project):
    platform = None

    try:
        json_info = json.load(open(PROJECT_INFO_PATH, "r"))
        if p.name in json_info.keys():
            platform = json_info[p.name].platform
        elif p.base in json_info.keys():
            platform = json_info[p.base].platform
        else:
            log.debug("Can not find the project's platform")
    except FileNotFoundError:
        log.exception("This file '%s' does not exists" % PROJECT_INFO_PATH)

    return platform


def update_platform_json_file(m: dict):
    pass


def get_platform_handler(p: Project):
    platform_handler = None

    if p.platform is None:
        log.error("The platform is None,please check the project's name")
        return None

    try:
        with open(PLATFORM_INFO_PATH, "r") as f_read:
            pl_info = json.load(f_read)
            for support_list in pl_info.keys():
                if p.platform in support_list:
                    name = pl_info[support_list].name
                    package = pl_info[support_list].package
                    import_module = __import__(package, fromlist=name)
                    module = import_module.get_full_path()
                    for attr in module.__dir__:
                        funcattrs = getattr(module, attr)
                        if callable(funcattrs):
                            platform_handler[attr] = funcattrs
                return platform_handler
    except:
        log.debug("Can not find file : '%s'" % PLATFORM_INFO_PATH)

    # Scan module info
    for dir_path in list_file_path(VPROJECTS_PATH, only_dir=True):
        for file_path in list_file_path(dir_path):
            module["name"] = os.path.basename(file_path).split()[0]
            start_index = file_path.find("vprjcore")
            end_index = file_path.find(".py")
            module["package"] = file_path[start_index:end_index].replace(
                os.sep, ".")

            import_module = __import__(
                module["package"], fromlist=[module["name"]])
            if hasattr(import_module, "get_platform"):
                module = import_module.get_platform()
                if hasattr(module, "support_list"):
                    if pl in module.support_list:
                        for attr in module.__dir__:
                            funcattrs = getattr(module, attr)
                            if callable(funcattrs):
                                platform_handler[attr] = funcattrs
                    update_platform_json_file(module)
                    return platform_handler
                else:
                    log.warning(
                        "This platform plug-in does not have the 'support_list' attribute")
            else:
                log.warning(
                    "This platform plug-in does not have the 'get_platform' attribute")

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
                        help="specify the new project as the board project")
    parser.add_argument(
        "--base", help="specify a new project to be created based on this")

    args = parser.parse_args()
    log.info(args.__dict__)
    return args.__dict__


if __name__ == "__main__":
    args_dict = parse_cmd()
    project = Project(args_dict)
