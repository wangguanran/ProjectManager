'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-14 20:01:07
@LastEditTime: 2020-02-20 00:35:38
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

PROJECT_INFO_PATH = "./.cache/project_info.json"


class Project(object):

    def __init__(self, project_name):
        log.debug("Project_Manager __init__ Im In")

        self.prj_info = {}
        # Get project info from file or database
        self.prj_info = self._get_prj_info(project_name)
        # Compatible operate platform
        self.platform = PlatformManager().compatible(self.prj_info)
        self.plugin_info = PluginManager().get_plugin_info()

    def _get_prj_info(self, project_name):
        prj_info = None

        # TODO Query the database to confirm whether the project data is updated
        # If yes, update the cache file. If no project information is found, an error will be returned
        log.debug("query database")
        # Save project info into cache(PROJECT_INFO_PATH)
        # with open(PROJECT_INFO_PATH, "a+") as f_write:
        #     json.dump(prj_info, f_write)
        #     f_write.write("\n")
        # END

        # Search project info in PROJECT_INFO_PATH first
        if os.path.exists(PROJECT_INFO_PATH):
            with open(PROJECT_INFO_PATH, "r") as f_read:
                lines = f_read.readlines()
            for line in lines:
                temp_info = json.loads(line)
                if(temp_info["name"] == project_name):
                    prj_info = temp_info
                    break

        if prj_info is None:
            log.error("The project('%s') info is None" % (project_name))
            sys.exit(-1)
        else:
            log.info("prj_info = %s" % (prj_info))
        return prj_info

    def dispatch(self, operate, arg_list):
        self.current_operate = operate
        self.arg_list = arg_list
        try:
            self.before_operate()
            self.platform.op_handler[operate](self)
            self.after_operate()
        except:
            log.exception("Error occurred!")

    def before_operate(self):
        for plugin in self.plugin_info.values():
            if self.current_operate in plugin.operate_list:
                plugin.operate_list[self.current_operate]["before"](self)

    def after_operate(self):
        for plugin in self.plugin_info.values():
            if self.current_operate in plugin.operate_list:
                plugin.operate_list[self.current_operate]["after"](self)


def parse_cmd():
    log.debug("argv = %s" % (sys.argv))
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', action="version", version="1.0")
    parser.add_argument('-d', '--debug', action="store_true", dest='isDebug')
    parser.add_argument("operate", help="supported operations")
    parser.add_argument("project_name", help="project name")
    parser.add_argument("arg_list", nargs="+", help="command info")
    args = parser.parse_args()
    log.info(args.__dict__)
    return args.__dict__


def create_fake_info(args_dict):
    prj_info = {}
    prj_info["name"] = args_dict["project_name"]
    prj_info["kernel_version"] = 3.18
    prj_info["android_version"] = 7.0
    prj_info["platform"] = "MT6735"
    with open(PROJECT_INFO_PATH, "a+") as f_write:
        json.dump(prj_info, f_write)
        f_write.write("\n")
        json.dump(prj_info, f_write)


if __name__ == "__main__":
    args_dict = parse_cmd()
    if args_dict["isDebug"]:
        if not os.path.exists(PROJECT_INFO_PATH):
            create_fake_info(args_dict)
    project = Project(args_dict['project_name'])
    project.dispatch(args_dict["operate"], args_dict["arg_list"])
