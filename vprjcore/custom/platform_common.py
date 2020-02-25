'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 22:36:07
@LastEditTime: 2020-02-25 21:46:54
@LastEditors: WangGuanran
@Description: Mtk Common Operate py file
@FilePath: /vprojects/vprjcore/custom/platform_common.py
'''

import os
import sys
import json
import shutil
import fnmatch

from vprjcore.common import log, get_full_path, list_file_path

NEW_PROJECT_DIR = get_full_path("new_project_base")
DEFAULT_KEYWORD = "demo"


class PlatformCommon(object):

    def __init__(self):
        self.support_list = [
            "MT6735",
            "MT6739",
        ]

    @staticmethod
    def new_project(project):
        log.debug("In!")

        platform_json_info = {}
        keyword = DEFAULT_KEYWORD
        project_name = project.project_name
        base_name = project.base_name
        is_board = project.args_dict.pop("is_board", False)
        log.debug("project_name = %s,is_board = %s,base_name = %s" %
                  (project_name, is_board, base_name))

        if project.by_new_project_base:
            basedir = get_full_path("new_project_base", base_name.lower())
        else:
            basedir = get_full_path(".", base_name.lower())
        destdir = get_full_path(project_name)
        log.debug("basedir = '%s' destdir = '%s'" % (basedir, destdir))

        if os.path.exists(basedir):
            if os.path.exists(destdir):
                log.error(
                    "The project has been created and cannot be created repeatedly")
            else:
                if project.by_new_project_base:
                    platform_json_info_path = get_full_path(
                        "new_project_base", "new_project_base.json")
                    log.debug("platform json info path = %s" %
                            platform_json_info_path)
                    with open(platform_json_info_path, "r") as f_read:
                        platform_json_info = json.load(f_read)
                        if hasattr(platform_json_info[base_name], "keyword"):
                            keyword = platform_json_info[base_name]["keyword"]
                else:
                    keyword = base_name

                shutil.copytree(basedir, destdir, symlinks="True")
                for p in list_file_path(destdir, list_dir=True):
                    if (not os.path.isdir(p)) and (fnmatch.fnmatch(os.path.basename(p), "env*.ini") or p.endswith(".patch")):
                        try:
                            log.debug("modify file content '%s'" % p)
                            with open(p, "r+") as f_rw:
                                content = f_rw.readlines()
                                f_rw.seek(0)
                                f_rw.truncate()
                                for line in content:
                                    line = line.replace(
                                        keyword, project_name)
                                    f_rw.write(line)
                        except:
                            log.error("Can not read file '%s'" % p)
                            return False
                    if keyword in os.path.basename(p):
                        p_dest = os.path.join(os.path.dirname(
                            p), os.path.basename(p).replace(keyword, project_name))
                        log.debug(
                            "rename src file = '%s' dest file = '%s'" % (p, p_dest))
                        os.rename(p, p_dest)
                return True
        else:
            log.error("No platform file, unable to create new project")

        return False

    @staticmethod
    def del_project(*args, **kwargs):
        log.debug("In!")

    @staticmethod
    def compile_project(*args, **kwargs):
        log.debug("In!")


# All platform scripts must contain this interface
def get_module():
    return PlatformCommon()
