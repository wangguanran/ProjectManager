"""
PatchOverride plugin module for project management.
"""
import os
import shutil

from src.log_manager import log
from src.utils import path_from_root, list_file_path

class PatchOverride:
    """
    Singleton class for patch override operations.
    """
    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, args_dict=None):
        """
        Initialize PatchOverride instance.
        """
        # No initialization needed
        # self.support_list = []
        # self.unsupported_list = []
        # ...
        # Remove unnecessary pass
        # pass

    def after_new_project(self, project):
        """
        Move directories (except 'po') into the overrides directory after creating a new project.
        """
        log.debug("In!")
        project_name = project.project_name
        prj_path = path_from_root(project_name)
        log.debug("project_name = %s,prj_path = '%s'", project_name, prj_path)
        destdir = os.path.join(prj_path, "po", f"po_{project_name}_bsp", "overrides")
        log.debug("destdir = '%s'", destdir)
        if not os.path.exists(destdir):
            os.makedirs(destdir)
        for dir_name in os.listdir(prj_path):
            dir_path = os.path.join(prj_path, dir_name)
            log.debug("dir name = %s", dir_path)
            if os.path.isdir(dir_path):
                if os.path.basename(dir_path) == "po":
                    continue
                log.debug("move dir_name='%s' destdir='%s'", dir_path, destdir)
                shutil.move(dir_path, destdir)
        # return self._modify_filename(destdir, project_name)
        return True

    def __modify_filename(self, path, project_name):
        """
        Recursively rename files containing project_name by appending '.override.base'.
        """
        for p in os.listdir(path):
            p_path = os.path.join(path, p)
            if os.path.isdir(p_path):
                self.__modify_filename(p_path, project_name)
            if project_name in os.path.basename(p_path):
                if "override" not in os.path.basename(p_path):
                    p_dest = os.path.join(path, os.path.basename(p_path) + ".override.base")
                    log.debug("modify p='%s' p_dest='%s'", p_path, p_dest)
                    os.rename(p_path, p_dest)
        return True

    def before_compile_project(self, project):
        """
        Prepare override files before compiling the project.
        """
        log.debug("In!")
        prj_name = project.project_name
        prj_po_path = path_from_root(prj_name, "po")
        log.debug("prj_name = %s,prj_path = '%s'", prj_name, prj_po_path)
        # destdir = os.path.join(prj_path, "po", "po_" +
        #                        prj_name + "_bsp", "overrides")
        # log.debug("destdir = '%s'" % destdir)

        if os.path.exists(prj_po_path):
            for po_dir_name in os.listdir(prj_po_path):
                override_path = os.path.join(
                    prj_po_path, po_dir_name, "overrides")
                log.debug("override path = %s", override_path)
                destdir = os.path.dirname(override_path)
                for file_name in list_file_path(destdir):
                    file_path = os.path.dirname(file_name)
                    # if not os.path.exists(abs_path):
                    #     os.makedirs(abs_path)
                    log.debug("file name = '%s' abs path = '%s'", file_name, file_path)
                    # shutil.copy(file_name, abs_path)

        else:
            log.warning("There is no po directory in this project")

        return True

    def after_compile_project(self, _):
        """
        Actions to perform after compiling the project.
        """
        log.debug("In!")
        return True


def get_module():
    """
    Return the PatchOverride singleton instance.
    """
    return PatchOverride()


def parse_cmd():
    """
    Parse command line arguments for the plugin (currently returns empty dict).
    """
    return {}


if __name__ == "__main__":
    cmd_args = parse_cmd()
    po = PatchOverride(cmd_args)
