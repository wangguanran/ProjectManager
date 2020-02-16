'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-14 20:01:07
@LastEditTime: 2020-02-15 21:30:21
@LastEditors: WangGuanran
@Description: project_manager py file
@FilePath: \vprojects\scripts\project_manager.py
'''

import sys
import time
import traceback
import argparse

from scripts.common import global_info
from scripts.operate_database import OperateDatabase
from scripts.log import log
from scripts.analyse import func_cprofile
from scripts.project import Project

PROJECT_INFO_PATH = "./.cache/project_info"
version = global_info['version']
isSupportDb = global_info['isSupportMysql'] | global_info['isSupportRedis']


class ProjectManager(object):

    def __init__(self, project_name):
        log.debug("Project_Manager __init__ Im In")
        self.prj_info = self._get_prj_info(project_name)
        log.debug("prj_info = %s" % (self.prj_info))
        self.project = Project(self.prj_info)

    def _get_prj_info(self, project_name):
        log.debug("In")
        prj_info = {}
        prj_info['name'] = project_name

        # Temp Data
        prj_info['platform'] = "MT6735"
        prj_info['kernel_version'] = 3.18
        prj_info['android_version'] = 7.1
        return prj_info
        # log.info("database support = %s" % (isSupportDb))
        # if (isSupportDb):
        #     # TODO 连接数据库
        #     op_db_handler = OperateDatabase()
        #     prj_info = op_db_handler.get_projects_info(project_name)
        # else:
        #     pass

    def get_project(self):
        return self.project


def parse_cmd():
    log.debug("argv = %s" % (sys.argv))
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', action="version",
                        version=global_info['version'])
    parser.add_argument("operate", help="supported operations")
    parser.add_argument("project_name", help="project name")
    parser.add_argument("--info", nargs="+", help="project info")
    args = parser.parse_args()
    log.info(args.__dict__)
    return args.__dict__


if __name__ == "__main__":
    argsdict = parse_cmd()
    project = ProjectManager(argsdict['project_name']).get_project()
    # project.dispatch(argsdict['operate'], argsdict['info'])
