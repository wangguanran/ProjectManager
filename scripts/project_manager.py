'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-14 20:01:07
@LastEditTime: 2020-02-15 21:30:21
@LastEditors: WangGuanran
@Description: project_manager py file
@FilePath: \vprojects\scripts\project_manager.py
'''

import os
import sys
import time
import traceback
import argparse
import json

from scripts.operate_database import OperateDatabase
from scripts.log import log
from scripts.analyse import func_cprofile
from scripts.platform.platform_manager import PlatformManager


class ProjectManager(object):

    def __init__(self, project_name):
        log.debug("Project_Manager __init__ Im In")

        self._project = {}
        # Get project info from file or database
        self._prj_info = self._get_prj_info(project_name)
        # Compatible operate platform
        self._platform_manager = PlatformManager()
        self._platform = self._platform_manager.compatible(self._prj_info)

        self._project["info"] = self._prj_info
        self._project["platform_manager"] = self._platform_manager
        self._project["platform"] = self._platform

    def _get_prj_info(self, project_name):
        log.debug("In")
        prj_info = {}
        PROJECT_INFO_PATH = "./.cache/project_info.json"

        if os.path.exists(PROJECT_INFO_PATH):
            with open(PROJECT_INFO_PATH, "r") as f_read:
                lines = f_read.readlines()
            for line in lines:
                temp_info = json.loads(line)
                if(temp_info["name"] == project_name):
                    prj_info = temp_info
                    break
        if len(prj_info) == 0:
            # Query Database
            log.debug("query database")
            # Save project info into cache(PROJECT_INFO_PATH)
            # json.dump(prj_info, open(PROJECT_INFO_PATH, "a"))

        if len(prj_info) == 0:
            log.error("The project('%s') info is None" % (project_name))
            sys.exit(-1)
        else:
            log.debug("prj_info = %s" % (prj_info))
        return prj_info

    def get_project(self):
        return self._project


def parse_cmd():
    log.debug("argv = %s" % (sys.argv))
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', action="version", version="1.0")
    parser.add_argument("operate", help="supported operations")
    parser.add_argument("project_name", help="project name")
    parser.add_argument("--info", nargs="+", help="project info")
    args = parser.parse_args()
    log.info(args.__dict__)
    return args.__dict__


if __name__ == "__main__":
    argsdict = parse_cmd()
    project_manager = ProjectManager(argsdict['project_name'])
    project = project_manager.get_project()
    project["platform"].dispatch(project["info"],argsdict)
