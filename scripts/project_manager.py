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

        self.project = {}
        # Get project info from file or database
        self.project["info"] = self._get_prj_info(project_name)
        # Compatible operate platform
        self.project["platform"] = PlatformManager().compatible(self.project["info"])

    def _get_prj_info(self, project_name):
        prj_info = None
        PROJECT_INFO_PATH = "./.cache/project_info.json"

        # TODO 查询数据库确认该项目数据是否有更新
        # 有则更新 PROJECT_INFO_PATH 缓存文件，未找到项目信息直接返回
        log.debug("query database")
        # Save project info into cache(PROJECT_INFO_PATH)
        # json.dump(prj_info, open(PROJECT_INFO_PATH, "a"))
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

    def get_project(self):
        return self.project

    def dispatch(self,args_dict):
        return self.project["platform"].op_handler[args_dict["operate"]](self.project["info"],args_dict["info"])


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
    args_dict = parse_cmd()
    project_manager = ProjectManager(args_dict['project_name'])
    project_manager.dispatch(args_dict)
