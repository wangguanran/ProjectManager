import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
import git
import json
import shutil
import datetime
import argparse
import threading
import fnmatch
from collections import OrderedDict

from common import func_cprofile, log, get_full_path, list_file_path, get_version
from common import PLATFORM_ROOT_PATH, VPRJ_CONFIG_PATH, VPRJCORE_PLUGIN_PATH

DEFAULT_KEYWORD = "demo"


class ProjectManager(object):
    """
    Project utility class. Provides project management and plugin operation features.
    """

    def new_project(self, name, type_, base=None):
        """
        Create a new project.
        Args:
            name (str): New project name.
            type_ (str): Type, 'board' or 'projects'.
            base (str): Base project name.
        Returns:
            bool: True if success, otherwise False.
        """
        keyword = DEFAULT_KEYWORD
        base = base or name
        basedir = get_full_path(base)
        destdir = get_full_path(name)
        log.debug("basedir = '%s' destdir = '%s'" % (basedir, destdir))

        if type_ not in ["board", "projects"]:
            log.error("--type must be 'board' or 'projects'")
            return False

        if os.path.exists(basedir):
            if os.path.exists(destdir):
                log.error("Project already exists, cannot create repeatedly.")
            else:
                with open(VPRJ_CONFIG_PATH, "r") as f_read:
                    platform_json_info = json.load(f_read)
                    if hasattr(platform_json_info[base], "keyword"):
                        keyword = platform_json_info[base]["keyword"]
                    else:
                        keyword = DEFAULT_KEYWORD if base == name else base
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
                                    line = line.replace(keyword, name)
                                    f_rw.write(line)
                        except Exception as e:
                            log.error(f"Cannot read file '{file_path}': {e}")
                            return False
                    if keyword in os.path.basename(file_path):
                        p_dest = os.path.join(os.path.dirname(file_path), os.path.basename(file_path).replace(keyword, name))
                        log.debug("Renaming src file = '%s' dest file = '%s'" % (file_path, p_dest))
                        os.rename(file_path, p_dest)
                return True
        else:
            log.error("Base project directory does not exist, unable to create new project.")
        return False

    def del_project(self, name, info_path=None):
        """
        Delete the specified project directory and update its status in the config file.
        Args:
            name (str): Project name.
            info_path (str): Config file path.
        Returns:
            bool: True if success, otherwise False.
        """
        log.debug("In del_project!")
        json_info = {}
        project_path = get_full_path(name)
        log.debug("project path = %s" % project_path)

        if os.path.exists(project_path):
            shutil.rmtree(project_path)
        else:
            log.warning("'%s' path already deleted." % name)
        if not info_path:
            info_path = getattr(self, 'info_path', None)
        try:
            with open(info_path, "r") as f_read:
                json_info = json.load(f_read)
                json_info[name]["status"] = "deleted"
            with open(info_path, "w+") as f_write:
                json.dump(json_info, f_write, indent=4)
        except Exception as e:
            log.error(f"Cannot find info file: {e}")
            return False
        return True

    def get_supported_operations(self):
        """
        Get all supported operation names from plugins.
        Returns:
            list: List of operation name strings.
        """
        op_handler = self._get_op_handler()
        return list(op_handler.keys())

    def execute_operation(self, operate, *args, **kwargs):
        """
        Execute the specified operation.
        Args:
            operate (str): Operation name.
            *args, **kwargs: Arguments for the operation.
        Returns:
            Operation return value.
        """
        op_handler = self._get_op_handler()
        if operate in op_handler:
            return op_handler[operate](*args, **kwargs)
        else:
            log.warning("Unsupported operation: %s" % operate)
            return None

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
    parser.add_argument("--base", help="base project name for new operation")
    args = parser.parse_args()
    return args.__dict__


def main():
    """
    Main entry point for the project manager CLI.
    """
    args_dict = parse_cmd()
    manager = ProjectManager()
    operate = args_dict["operate"]
    name = args_dict["name"]
    type_ = args_dict.get("type")
    base = args_dict.get("base")
    if operate == "new":
        manager.new_project(name=name, type_=type_, base=base)
    elif operate == "delete":
        manager.del_project(name=name)
    else:
        # Try to execute as plugin operation
        result = manager.execute_operation(operate, name)
        if result is None:
            log.error(f"Operation '{operate}' is not supported.")


if __name__ == "__main__":
    main()
