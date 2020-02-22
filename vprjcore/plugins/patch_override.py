'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 17:18:01
@LastEditTime: 2020-02-22 09:26:35
@LastEditors: WangGuanran
@Description: patch override py file
@FilePath: \vprojects\vprjcore\plugins\patch_override.py
'''
import os
import shutil

from vprjcore.common import log


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
        prj_path = os.path.join(os.getcwd(), project_name)
        log.debug("project_name = %s,prj_path = %s" % (project_name, prj_path))
        # e:\vprojects\tnz801\po\po_tnz801_bsp\overrides\...
        destdir = os.path.join(prj_path, "po", "po_" +
                               project_name+"_bsp", "overrides")
        log.debug("destdir = %s" % (destdir))
        if not os.path.exists(destdir):
            os.makedirs(destdir)
        for dir in os.listdir(prj_path):
            dir = os.path.join(prj_path, dir)
            if os.path.isdir(dir):
                if os.path.basename(dir) == "po":
                    continue
                shutil.move(dir, destdir)
        self._modify_filename(destdir, project_name)

    def _modify_filename(self, path, project_name):
        for p in os.listdir(path):
            p = os.path.join(path, p)
            if os.path.isdir(p):
                self._modify_filename(p, project_name)
            if project_name in os.path.basename(p):
                if not "override" in os.path.basename(p):
                    p_dest = os.path.join(p, p+".override.base")
                    os.rename(p, p_dest)

    def before_compile(self, project):
        log.debug("In!")

    def after_compile(self, project):
        log.debug("In!")


# All plugin must contain this interface
def get_module():
    return PatchOverride()
