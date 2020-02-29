'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 22:36:07
@LastEditTime: 2020-02-29 17:10:56
@LastEditors: WangGuanran
@Description: Mtk Common Operate py file
@FilePath: /vprojects/vprjcore/MTK/mtk_common.py
'''

import os
import sys
import json
import shutil
import fnmatch

from vprjcore.common import log, get_full_path, list_file_path
from vprjcore.common import PROJECT_INFO_PATH, NEW_PROJECT_DIR, DEFAULT_KEYWORD, BOARD_INFO_PATH
from vprjcore.project import Project


class PlatformCommon(object):

    def __init__(self):
        self.support_list = [
            "MT6735",
            "MT6739",
        ]

    @staticmethod
    def new_project(p: Project):
        keyword = DEFAULT_KEYWORD
        basedir = get_full_path(p.base)
        destdir = get_full_path(p.name)
        log.debug("basedir = '%s' destdir = '%s'" % (basedir, destdir))

        if os.path.exists(basedir):
            if os.path.exists(destdir):
                log.error(
                    "The project has been created and cannot be created repeatedly")
            else:
                with open(PROJECT_INFO_PATH, "r") as f_read:
                    platform_json_info = {}
                    platform_json_info = json.load(f_read)
                    if hasattr(platform_json_info[p.base], "keyword"):
                        keyword = platform_json_info[p.base]["keyword"]
                    else:
                        if p.base.upper() == p.platform.upper():
                            keyword = DEFAULT_KEYWORD
                        else:
                            keyword = p.base
                log.debug("keyword='%s'" % keyword)

                shutil.copytree(basedir, destdir, symlinks=True)
                for file_path in list_file_path(destdir, list_dir=True):
                    if (fnmatch.fnmatch(os.path.basename(file_path), "env*.ini")
                            or file_path.endswith(".patch")):
                        try:
                            log.debug("modify file content '%s'" % file_path)
                            with open(file_path, "r+") as f_rw:
                                content = f_rw.readlines()
                                f_rw.seek(0)
                                f_rw.truncate()
                                for line in content:
                                    line = line.replace(keyword, p.name)
                                    f_rw.write(line)
                        except:
                            log.error("Can not read file '%s'" % file_path)
                            return False
                    if keyword in os.path.basename(file_path):
                        p_dest = os.path.join(os.path.dirname(
                            file_path), os.path.basename(file_path).replace(keyword, p.name))
                        log.debug(
                            "rename src file = '%s' dest file = '%s'" % (file_path, p_dest))
                        os.rename(file_path, p_dest)
                return True
        else:
            log.error("No platform file, unable to create new project")

        return False

    @staticmethod
    def del_project(p: Project):
        log.debug("In!")

        json_info = {}
        project_path = get_full_path(p.name)
        log.debug("project path = %s" % project_path)

        if os.path.exists(project_path):
            shutil.rmtree(project_path)
        else:
            log.warning("The '%s' path is already delete" % p.name)
        try:
            with open(p.info_path, "r") as f_read:
                json_info = json.load(f_read)
                json_info[p.name]["is_delete"] = True
            with open(p.info_path, "w+") as f_write:
                json.dump(json_info, f_write, indent=4)
        except:
            log.exception("Can not find info file")
            return False

        return True

    @staticmethod
    def compile_project(project):
        log.debug("In!")
        return True


# All platform scripts must contain this interface
def get_platform():
    return PlatformCommon()
