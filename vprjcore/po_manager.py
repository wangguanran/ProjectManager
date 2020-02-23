'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 17:18:01
@LastEditTime: 2020-02-23 10:30:13
@LastEditors: WangGuanran
@Description: patch override py file
@FilePath: \vprojects\vprjcore\po_manager.py
'''
import os
import shutil

from vprjcore.common import log, get_full_path


class PatchOverride(object):
    def __init__(self):
        # self.support_list=[
        #     ""
        # ]
        # self.unsupported_list=[
        #     ""
        # ]
        pass

    def after_new_project(self, project):
        log.debug("In!")
        project_name = project.project_name
        prj_path = get_full_path(project_name)
        log.debug("project_name = %s,prj_path = '%s'" % (project_name, prj_path))
        destdir = os.path.join(prj_path, "po", "po_" +
                               project_name + "_bsp", "overrides")
        log.debug("destdir = '%s'" % destdir)
        if not os.path.exists(destdir):
            os.makedirs(destdir)
        for dir_name in os.listdir(prj_path):
            dir_name = os.path.join(prj_path, dir_name)
            if os.path.isdir(dir_name):
                if os.path.basename(dir_name) == "po":
                    continue
                log.debug("move dir_name='%s' destdir='%s'" % (dir, destdir))
                shutil.move(dir_name, destdir)
        self._modify_filename(destdir, project_name)

    def _modify_filename(self, path, project_name):
        for p in os.listdir(path):
            p = os.path.join(path, p)
            if os.path.isdir(p):
                self._modify_filename(p, project_name)
            if project_name in os.path.basename(p):
                if "override" not in os.path.basename(p):
                    p_dest = os.path.join(p, p + ".override.base")
                    log.debug("modify p='%s' p_dest='%s'" % (p, p_dest))
                    os.rename(p, p_dest)

    def before_compile_project(self, project):
        log.debug("In!")

    def after_compile_project(self, project):
        log.debug("In!")


# All plugin must contain this interface
def get_module():
    return PatchOverride()
