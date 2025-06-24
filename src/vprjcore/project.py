import os
import sys
import git
import json
import shutil
import datetime
import argparse
import threading
import fnmatch
from collections import OrderedDict

from vprjcore.common import func_cprofile, log, get_full_path, list_file_path, get_version
from vprjcore.common import PLATFORM_ROOT_PATH, VPRJ_CONFIG_PATH, VPRJCORE_PLUGIN_PATH

DEFAULT_KEYWORD = "demo"


class Project(object):
    """
    Project management class. Handles project creation, deletion, and dynamic plugin operation dispatch.
    """

    def __init__(self, args_dict: dict):
        """
        Initialize Project instance and execute the specified operation.
        Args:
            args_dict (dict): Command line arguments as a dictionary.
        """
        operate = args_dict.pop("operate").lower()
        self.name = args_dict.pop("name").lower()
        self.type = args_dict.pop("type", None)
        if operate == "new":
            if self.type not in ["board", "projects"]:
                log.error("When operate is 'new', --type must be 'board' or 'projects'.")
                sys.exit(1)
        op_handler = self._get_op_handler()
        self.executed(operate, op_handler)

    @func_cprofile
    def executed(self, operate, op_handler):
        """
        Execute the operation if it exists in the operation handler.
        Args:
            operate (str): Operation name.
            op_handler (dict): Operation name to function mapping.
        """
        if operate in op_handler.keys():
            if op_handler[operate](self):
                log.info("Operation succeeded!")
            else:
                log.info("Operation failed!")
        else:
            log.warning("Operation not supported.")

    def new_project(self):
        """
        Create a new project by copying from a base project directory, replacing keywords, and renaming files as needed.
        Returns:
            bool: True if successful, False otherwise.
        """
        keyword = DEFAULT_KEYWORD
        basedir = get_full_path(self.base)
        destdir = get_full_path(self.name)
        log.debug("basedir = '%s' destdir = '%s'" % (basedir, destdir))

        if os.path.exists(basedir):
            if os.path.exists(destdir):
                log.error("The project has already been created and cannot be created repeatedly.")
            else:
                with open(VPRJ_CONFIG_PATH, "r") as f_read:
                    platform_json_info = json.load(f_read)
                    if hasattr(platform_json_info[self.base], "keyword"):
                        keyword = platform_json_info[self.base]["keyword"]
                    else:
                        keyword = DEFAULT_KEYWORD if self.base == self.name else self.base
                log.debug("keyword='%s'" % keyword)

                shutil.copytree(basedir, destdir, symlinks=True)
                for file_path in list_file_path(destdir, list_dir=True):
                    if (fnmatch.fnmatch(os.path.basename(file_path), "env*.ini")
                            or file_path.endswith(".patch")):
                        try:
                            log.debug("Modifying file content '%s'" % file_path)
                            with open(file_path, "r+") as f_rw:
                                content = f_rw.readlines()
                                f_rw.seek(0)
                                f_rw.truncate()
                                for line in content:
                                    line = line.replace(keyword, self.name)
                                    f_rw.write(line)
                        except:
                            log.error("Cannot read file '%s'" % file_path)
                            return False
                    if keyword in os.path.basename(file_path):
                        p_dest = os.path.join(os.path.dirname(file_path), os.path.basename(file_path).replace(keyword, self.name))
                        log.debug("Renaming src file = '%s' dest file = '%s'" % (file_path, p_dest))
                        os.rename(file_path, p_dest)
                return True
        else:
            log.error("Base project directory does not exist, unable to create new project.")

        return False

    def del_project(self):
        """
        Delete the specified project directory and update its status in the config file if possible.
        Returns:
            bool: True if successful, False otherwise.
        """
        log.debug("In del_project!")
        json_info = {}
        project_path = get_full_path(self.name)
        log.debug("project path = %s" % project_path)

        if os.path.exists(project_path):
            shutil.rmtree(project_path)
        else:
            log.warning("The '%s' path is already deleted." % self.name)
        try:
            with open(self.info_path, "r") as f_read:
                json_info = json.load(f_read)
                json_info[self.name]["status"] = "deleted"
            with open(self.info_path, "w+") as f_write:
                json.dump(json_info, f_write, indent=4)
        except:
            log.exception("Cannot find info file.")
            return False

        return True

    def _get_op_handler(self):
        """
        Dynamically load all callable functions from scripts in vprojects/scripts as operation handlers.
        Returns:
            dict: Mapping from operation name to function.
        """
        op_handler = {}
        scripts_dir = get_full_path("scripts")
        if not os.path.exists(scripts_dir):
            log.warning(f"scripts directory does not exist: {scripts_dir}")
            return op_handler
        for file_name in os.listdir(scripts_dir):
            if not file_name.endswith(".py") or file_name.startswith("_"):
                continue
            script_path = os.path.join(scripts_dir, file_name)
            module_name = os.path.splitext(file_name)[0]
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(module_name, script_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                # Collect all callable functions
                for attr in dir(mod):
                    if attr.startswith("_"):
                        continue
                    func = getattr(mod, attr)
                    if callable(func):
                        op_handler[attr] = func
            except Exception as e:
                log.error(f"Failed to load script: {script_path}, error: {e}")
                continue
        return op_handler


def parse_cmd():
    """
    Parse command line arguments for the project manager.
    Returns:
        dict: Parsed arguments as a dictionary.
    """
    log.debug("argv = %s" % sys.argv)
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action="version", version=get_version())
    parser.add_argument("operate", choices=["build", "new", "delete"], help="supported operations: build/new/delete")
    parser.add_argument("name", help="project or board name")
    parser.add_argument("--type", help="type for new operation: board or projects", choices=["board", "projects"], default=None)
    args = parser.parse_args()
    return args.__dict__


def main():
    """
    Main entry point for the project manager CLI.
    """
    args_dict = parse_cmd()
    project = Project(args_dict)


if __name__ == "__main__":
    main()
