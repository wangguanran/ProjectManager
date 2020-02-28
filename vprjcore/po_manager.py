'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 17:18:01
@LastEditTime: 2020-02-26 18:33:43
@LastEditors: WangGuanran
@Description: patch override py file
@FilePath: /vprojects/vprjcore/po_manager.py
'''
import os
import shutil

from vprjcore.common import log, get_full_path, PLATFORM_ROOT_PATH, list_file_path


class PatchOverride(object):

    """
    Singleton mode
    """
    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, args_dict=None):
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
        log.debug("project_name = %s,prj_path = '%s'" %
                  (project_name, prj_path))
        destdir = os.path.join(prj_path, "po", "po_" +
                               project_name + "_bsp", "overrides")
        log.debug("destdir = '%s'" % destdir)
        if not os.path.exists(destdir):
            os.makedirs(destdir)
        for dir_name in os.listdir(prj_path):
            dir_name = os.path.join(prj_path, dir_name)
            log.debug("dir name = %s" % dir_name)
            if os.path.isdir(dir_name):
                if os.path.basename(dir_name) == "po":
                    continue
                log.debug("move dir_name='%s' destdir='%s'" %
                          (dir_name, destdir))
                shutil.move(dir_name, destdir)
        # return self._modify_filename(destdir, project_name)
        return True

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
        return True

    def before_compile_project(self, project):
        log.debug("In!")
        prj_name = project.project_name
        prj_po_path = get_full_path(prj_name, "po")
        log.debug("prj_name = %s,prj_path = '%s'" % (prj_name, prj_po_path))
        # destdir = os.path.join(prj_path, "po", "po_" +
        #                        prj_name + "_bsp", "overrides")
        # log.debug("destdir = '%s'" % destdir)

        if os.path.exists(prj_po_path):
            for po_dir_name in os.listdir(prj_po_path):
                override_path = os.path.join(
                    prj_po_path, po_dir_name, "overrides")
                log.debug("override path = %s" % override_path)
                destdir = os.path.dirname()
                for file_name in list_file_path(destdir):
                    file_path = os.path.dirname(file_name)
                    abs_path = os.path.join(PLATFORM_ROOT_PATH, file_path)
                    # if not os.path.exists(abs_path):
                    #     os.makedirs(abs_path)
                    log.debug("file name = '%s' abs path = '%s'" %
                              (file_name, abs_path))
                    # shutil.copy(file_name, abs_path)

        else:
            log.warning("There is no po directory in this project")

        return True

    def after_compile_project(self, project):
        log.debug("In!")
        return True


# All plugin must contain this interface
def get_module():
    return PatchOverride()


def parse_cmd():
    return args_dict


if __name__ == "__main__":
    args_dict = parse_cmd()
    po = PatchOverride(args_dict)
