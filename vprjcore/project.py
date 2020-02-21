'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-14 20:01:07
@LastEditTime: 2020-02-21 17:52:41
@LastEditors: WangGuanran
@Description: project_manager py file
@FilePath: \vprojects\vprjcore\project.py
'''

import os
import sys
import time
import traceback
import argparse
import json
from functools import partial

from vprjcore.log import log
from vprjcore.analyse import func_cprofile
from vprjcore.common import load_module
# from vprjcore.platform_manager import PlatformManager
# from vprjcore.plugin_manager import PluginManager
# from vprjcore.project_manager import ProjectManager

VPRJCORE_VERSION = "0.0.1"
get_full_path = partial(os.path.join, os.getcwd(), "vprjcore")
VPRJCORE_MANAGER_PATH = get_full_path()


class Project(object):

    def __init__(self, args_dict, auto_dispatch=True):
        self._manager_info = {}
        # self._load_manager()
        load_module(self,VPRJCORE_MANAGER_PATH,1)

        self.args_dict = args_dict
        self.operate = args_dict.pop("operate").lower()
        self.project_name = args_dict.pop("project_name").lower()
        log.debug("project_name = %s,operate = %s" %
                  (self.project_name, self.operate))

        # # Get project info from file or database
        # # self.prj_info = ProjectManager().get_prj_info(self.project_name)
        # # Compatible operate platform
        # self.platform_name = ProjectManager().get_platform_name(self)
        # # self.platform_name = args_dict.pop("platform", None).upper()
        # # if self.platform_name is None:
        # #     if self.prj_info is None:
        # #         log.error("Can not find platform name!")
        # #         sys.exit(-1)
        # #     else:
        # #         self.platform_name = self.prj_info["platform_name"]
        # self.platform_handler = PlatformManager().compatible(self.platform_name)
        # # Get manager_module information
        # self.plugin_info_dict = PluginManager().get_plugin_info()

        # if auto_dispatch:
        #     self.dispatch(self.operate, args_dict)

    def _load_manager(self):
        log.debug("_load_manager in")
        for filename in os.listdir(VPRJCORE_MANAGER_PATH):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
            if "manager" in filename:
                log.debug("register manager = %s" % (filename))
                manager_name = os.path.splitext(filename)[0]
                log.debug("manager_name = %s" % (manager_name))
                package_name = 'vprjcore.'+manager_name
                log.debug("package_name = %s" % (package_name))
                manager_module = __import__(
                    package_name, fromlist=[manager_name])

                if hasattr(manager_module, "get_manager"):
                    manager = manager_module.get_manager()
                    manager.filename = manager_module.__file__
                    manager.manager_name = manager_name
                    manager.package_name = package_name
                    self._register_manager(manager)
                else:
                    log.warning("file '%s' does not have 'get_manager',fail to register manager_module" %
                                (manager_module.__file__))

    def _register_manager(self, manager):
        attrlist = dir(manager)
        log.debug(attrlist)

        manager.operate_list = {}
        for attr in attrlist:
            if not attr.startswith("_"):
                funcaddr = getattr(manager, attr)
                if callable(funcaddr):
                    if "_" in attr:
                        index, operate = attr.split(sep="_",maxsplit=1)
                        if not operate in manager.operate_list.keys():
                            manager.operate_list[operate] = {}
                        manager.operate_list[operate][index] = funcaddr
        log.debug(manager.operate_list)
        if manager.operate_list:
            log.debug("register '%s' successfully!" % (manager.manager_name))
            self._manager_info[manager.manager_name] = manager
        else:
            log.warning("No matching function in '%s'" % (manager.manager_name))

    @func_cprofile
    def dispatch(self, operate, args_dict):
        '''
        @description: Distribute operations to platform interface
        @param {type}   operate :operation command(str)
                        args_dict:parameter dictionary(dict)
        @return: None
        '''
        try:
            self._before_operate()
            ret = self.platform_handler[operate](self, args_dict)
            if ret:
                self._after_operate()
        except:
            log.exception("Error occurred!")

    def _check_required_list(self, plugin):
        '''
        @description: Check support_list and unsupported_list in the plug-in
                        to determine if this platform is supported
        @param {type} plugin:plugin information
        @return: is supported(true or false)
        '''
        is_in_support_list = False
        is_in_unsupported = False
        is_has_support_list = False
        is_has_unsupported = False

        if hasattr(plugin, "support_list"):
            is_has_support_list = True
            if self.platform_name in plugin.support_list:
                is_in_support_list = True
        if hasattr(plugin, "unsupported_list"):
            is_has_unsupported = True
            if self.platform_name in plugin.unsupported_list:
                is_in_unsupported = True

        if is_in_support_list and is_in_unsupported:
            log.warning(
                "('%s')The platform exists in both the support list and the unsupported list" % (plugin.pluginName))
            plugin.support_list.remove(self.platform_name)
            plugin.unsupported_list.remove(self.platform_name)
            return False
        elif is_in_support_list or (is_has_unsupported and not is_in_unsupported):
            return True
        elif is_in_unsupported or is_has_support_list:
            return False
        else:
            # If support_list and unsupported_list are not specified in the plug-in,
            #   all platforms are supported by default
            return True

    def _polling_manager_list_and_execute(self, exec_pos):
        pass

    def _polling_plugin_list_and_execute(self, exec_pos):
        '''
        @description: Poll to check if the plug-in list has operations
                        at the location specified by exec_pos
        @param {type} exec_pos:execution position
        @return: None
        '''
        for plugin in self.plugin_info_dict.values():
            if self._check_required_list(plugin):
                if self.operate in plugin.operate_list:
                    if exec_pos in plugin.operate_list[self.operate]:
                        plugin.operate_list[self.operate][exec_pos](
                            self)

    def _before_operate(self):
        '''
        @description: Perform operation in 'before' position
        @param {type} None
        @return: None
        '''
        self._polling_manager_list_and_execute("before")
        self._polling_plugin_list_and_execute("before")

    def _after_operate(self):
        '''
        @description: Perform operation in 'after' position
        @param {type} None
        @return: None
        '''
        self._polling_plugin_list_and_execute("after")
        self._polling_manager_list_and_execute("after")


def parse_cmd():
    '''
    @description: Parsing command line parameters
    @param {type} None
    @return: arg list(dict)
    '''
    log.debug("argv = %s" % (sys.argv))
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', action="version",
                        version=VPRJCORE_VERSION)
    # parser.add_argument('-d', '--debug', action="store_true",
    #                     dest='is_debug', help="debug switch")
    parser.add_argument("operate", help="supported operations")
    parser.add_argument("project_name", help="project name")
    # parser.add_argument("arg_list", nargs="+", help="command info")

    group = parser.add_argument_group("new_project")
    group.add_argument('-b', action="store_true", dest="is_board",
                       help="specify the new project as the board project")
    group.add_argument(
        "--platform", help="specify a new project to be created based on this")
    group.add_argument(
        "--base", help="specify a new project to be created based on this")

    args = parser.parse_args()
    log.info(args.__dict__)
    return args.__dict__


if __name__ == "__main__":
    args_dict = parse_cmd()
    project = Project(args_dict)
    # project.dispatch(args_dict["operate"], args_dict)
