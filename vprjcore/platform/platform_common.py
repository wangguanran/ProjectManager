'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 22:36:07
@LastEditTime: 2020-02-22 16:44:55
@LastEditors: WangGuanran
@Description: Mtk Common Operate py file
@FilePath: \vprojects\vprjcore\platform\platform_common.py
'''

import os
import sys
import shutil
import fnmatch

from vprjcore.common import log, get_full_path, list_file_path

NEW_PROJECT_DIR = get_full_path("new_project_base")
DEFAULT_BASE_NAME = "demo"


class PlatformCommon(object):

    def __init__(self):
        self.support_list = [
            "MT6735",
            "MT6739",
        ]

    def new_project(self, project):
        log.debug("In!")
        project_name = project.project_name
        base_name = project.base_name
        is_board = project.args_dict.pop("is_board", False)
        log.debug("project_name = %s,is_board = %s,base_name = %s" %
                  (project_name, is_board, base_name))

        if project.by_new_project_base:
            basedir = get_full_path("new_project_base", base_name.lower())
        else:
            basedir = get_full_path(".", base_name.lower())
        destdir = os.path.join(os.getcwd(), project_name)
        log.debug("basedir = %s destdir = %s" % (basedir, destdir))
        if os.path.exists(basedir):
            if os.path.exists(destdir):
                log.error(
                    "The project has been created and cannot be created repeatedly")
            else:
                shutil.copytree(basedir, destdir, symlinks="True")
                for p in list_file_path(destdir, list_dir=True):
                    if (not os.path.isdir(p)) and (fnmatch.fnmatch(p,"env*.ini") or p.endswith(".patch")):
                        try:
                            with open(p, "r+") as f_rw:
                                content = f_rw.readlines()
                                f_rw.seek(0)
                                f_rw.truncate()
                                for line in content:
                                    line = line.replace(
                                        base_name, project_name)
                                    f_rw.write(line)
                        except:
                            log.error("Can not read file '%s'" % (p))
                            sys.exit(-1)
                    if base_name in os.path.basename(p):
                        p_dest = os.path.join(os.path.dirname(
                            p), os.path.basename(p).replace(base_name, project_name))
                        os.rename(p, p_dest)
                log.debug("new project '%s' down!" % (project_name))
                return True
        else:
            log.error("No platform file, unable to create new project")

        return False

    def del_project(self, *args, **kwargs):
        log.debug("In!")

    def compile_project(self, *args, **kwargs):
        log.debug("In!")


# All platform scripts must contain this interface
def get_module():
    return PlatformCommon()
