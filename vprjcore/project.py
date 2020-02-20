'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-14 20:01:07
@LastEditTime: 2020-02-20 22:57:37
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

from vprjcore.operate_database import OperateDatabase
from vprjcore.log import log
from vprjcore.analyse import func_cprofile
from vprjcore.platform_manager import PlatformManager
from vprjcore.plugin_manager import PluginManager

VPRJCORE_VERSION = "0.0.1"
PROJECT_INFO_PATH = "./.cache/project_info.json"


class Project(object):

    def __init__(self, project_name):
        log.debug("Project_Manager __init__ Im In")

        self.prj_info = {}
        # Get project info from file or database
        self.prj_info = self._get_prj_info(project_name)
        # Compatible operate platform
        self.platform = PlatformManager().compatible(self.prj_info)
        # Get plugin information
        self.plugin_info = PluginManager().get_plugin_info()

    def _get_prj_info(self, project_name):
        '''
        @description: get project information from cache file or db
        @param {type} project_name:project name(str)
        @return: project info(dict)
        '''
        prj_info = None

        # TODO Query the database to confirm whether the project data is updated
        # If yes, update the cache file. If no project information is found, an error will be returned
        log.debug("query database")
        # Save project info into cache(PROJECT_INFO_PATH)
        # with open(PROJECT_INFO_PATH, "w+") as f_write:
        #     json.dump(prj_info, f_write)
        #     f_write.write("\n")
        # END

        # Search project info in PROJECT_INFO_PATH first
        if os.path.exists(PROJECT_INFO_PATH):
            json_info = json.load(open(PROJECT_INFO_PATH, "r"))
            for prj_name, temp_info in json_info.items():
                if(prj_name.lower() == project_name.lower()):
                    prj_info = temp_info

        if prj_info is None:
            log.error("The project('%s') info is None" % (project_name))
            sys.exit(-1)
        else:
            prj_info["name"] = project_name.lower()
            log.info("prj_info = %s" % (prj_info))
        return prj_info

    def dispatch(self, operate, arg_list):
        '''
        @description: Distribute operations to platform interface
        @param {type}   operate :operation command(str)
                        arg_list:parameter list(list)
        @return: None
        '''
        self.current_operate = operate
        self.arg_list = arg_list
        try:
            self._before_operate()
            self.platform.op_handler[operate](self)
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
        isInSupportList = False
        isInUnsupported = False
        if hasattr(plugin, "support_list"):
            if self.prj_info["platform_name"] in plugin.support_list:
                isInSupportList = True
        if hasattr(plugin, "unsupported_list"):
            if self.prj_info["platform_name"] in plugin.unsupported_list:
                isInUnsupported = True

        if isInSupportList and isInUnsupported:
            log.warning(
                "('%s')The platform exists in both the support list and the unsupported list" % (plugin.pluginName))
            plugin.support_list.remove(self.prj_info["platform_name"])
            plugin.unsupported_list.remove(self.prj_info["platform_name"])
            return False
        elif isInSupportList:
            return True
        elif isInUnsupported:
            return False
        else:
            # If support_list and unsupported_list are not specified in the plug-in,
            #   all platforms are supported by default
            return True

    def _polling_plugin_list_and_execute(self, exec_pos):
        '''
        @description: Poll to check if the plug-in list has operations
                        at the location specified by exec_pos
        @param {type} exec_pos:execution position
        @return: None
        '''
        for plugin in self.plugin_info.values():
            if self._check_required_list(plugin):
                if self.current_operate in plugin.operate_list:
                    if exec_pos in plugin.operate_list[self.current_operate]:
                        plugin.operate_list[self.current_operate][exec_pos](
                            self)

    def _before_operate(self):
        '''
        @description: Perform operation in 'before' position
        @param {type} None
        @return: None
        '''
        self._polling_plugin_list_and_execute("before")

    def _after_operate(self):
        '''
        @description: Perform operation in 'after' position
        @param {type} None
        @return: None
        '''
        self._polling_plugin_list_and_execute("after")


def parse_cmd():
    '''
    @description: Parsing command line parameters
    @param {type} None
    @return: arg list(dict)
    '''
    log.debug("argv = %s" % (sys.argv))
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', action="version", version=VPRJCORE_VERSION)
    parser.add_argument('-d', '--debug', action="store_true", dest='is_debug',help="debug switch")
    parser.add_argument("operate", help="supported operations")
    parser.add_argument("project_name", help="project name")
    # parser.add_argument("arg_list", nargs="+", help="command info")

    group = parser.add_argument_group("new_project")
    group.add_argument('-b',action="store_true",dest="is_board",help="specify the new project as the board project")
    group.add_argument("--base",help="specify a new project to be created based on this")

    args = parser.parse_args()
    log.info(args.__dict__)
    return args.__dict__


def create_fake_info(args_dict):
    '''
    @description: Create some fake information to debug(write to json file)
    @param {type} args_dict:parameter list
    @return: None
    '''
    json_info = {}
    prj_info = {}
    if os.path.exists(PROJECT_INFO_PATH):
        with open(PROJECT_INFO_PATH, "r") as f_read:
            try:
                if os.path.getsize(PROJECT_INFO_PATH):
                    json_info = json.load(f_read)
                else:
                    log.warning("json file size is zero")
            except:
                log.exception("Json file format error")
            f_read.close()

    for prj_name, temp_info in json_info.items():
        if(prj_name == args_dict["project_name"]):
            prj_info = temp_info
    if len(prj_info) == 0:
        log.debug("Insert fake project info")
        # prj_info["name"] = args_dict["project_name"]
        prj_info["kernel_version"] = 3.18
        prj_info["android_version"] = 7.0
        prj_info["platform_name"] = "MT6735"

        json_info[args_dict["project_name"].lower()] = prj_info
        with open(PROJECT_INFO_PATH, "w+") as f_write:
            json.dump(json_info, f_write, indent=4)
            f_write.close()
    else:
        log.debug("project info is already exist,skip this step")


if __name__ == "__main__":
    args_dict = parse_cmd()
    if args_dict["is_debug"]:
        create_fake_info(args_dict)
    project = Project(args_dict['project_name'])
    project.dispatch(args_dict["operate"], args_dict)
