'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-14 20:01:07
@LastEditTime: 2020-02-22 21:57:35
@LastEditors: WangGuanran
@Description: project_manager py file
@FilePath: \vprojects\vprjcore\project.py
'''

import argparse
import os
import sys

from vprjcore.common import load_module, func_cprofile, log, get_full_path

VPRJCORE_VERSION = "0.0.1"
VPRJCORE_PLUGIN_PATH = get_full_path("vprjcore")


class Project(object):

    def __init__(self, args_dict: dict, auto_dispatch=True):
        """

        :type args_dict: dict
        """
        self.platform_handler = None
        self.plugin_list = load_module(VPRJCORE_PLUGIN_PATH, 1)
        log.debug("plugin list = %s" % self.plugin_list)

        self.args_dict = args_dict
        self.operate = args_dict.pop("operate").lower()
        self.project_name = args_dict.pop("project_name").lower()
        log.debug("project_name = %s,operate = %s" %
                  (self.project_name, self.operate))

        if auto_dispatch:
            self.dispatch()

    @func_cprofile
    def dispatch(self):
        """
        @description: Distribute operations to platform interface
        @param {type} None
        @return: None
        """
        try:
            self._before_operate()
            ret = self.platform_handler[self.operate](self)
            if ret:
                self._after_operate()
        except:
            log.exception("Error occurred!")
        pass

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
                    plugin.operate_list[self.operate][exec_pos](self)
                    del plugin.operate_list[self.operate][exec_pos]

    def _before_operate(self):
        """
        @description: Perform operation in 'before' position
        @param {type} None
        @return: None
        """
        self._polling_plugin_list_and_execute("before")

    def _after_operate(self):
        """
        @description: Perform operation in 'after' position
        @param {type} None
        @return: None
        """
        self._polling_plugin_list_and_execute("after")


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

    group = parser.add_argument_group("new_project")
    group.add_argument('-b', action="store_true", dest="is_board",
                       help="specify the new project as the board project")
    group.add_argument(
        "--base", help="specify a new project to be created based on this")

    args = parser.parse_args()
    log.info(args.__dict__)
    return args.__dict__


if __name__ == "__main__":
    args_dict = parse_cmd()
    project = Project(args_dict)
