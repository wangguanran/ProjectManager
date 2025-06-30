import cProfile
import logging
import logging.config
import os
import pstats
import shutil
import time
from functools import partial, wraps
import sys
import git
import json
import argparse
import threading
import fnmatch
from collections import OrderedDict
try:
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata
import toml

if os.path.basename(os.getcwd()) == "vprojects":
    get_full_path = partial(os.path.join, os.getcwd())
elif os.path.basename(os.getcwd()) in ["scripts"]:
    get_full_path = partial(os.path.join, os.path.dirname(os.getcwd()))
else:
    get_full_path = partial(os.path.join, os.getcwd(), "vprojects")

def get_version():
    try:
        # 兼容PyInstaller打包和源码运行
        if hasattr(sys, '_MEIPASS'):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        pyproject_path = os.path.join(base_dir, 'pyproject.toml')
        if not os.path.exists(pyproject_path):
            pyproject_path = os.path.join(base_dir, '../pyproject.toml')
        data = toml.load(pyproject_path)
        return data["project"]["version"]
    except Exception:
        return "0.0.0-dev"

LOG_PATH = get_full_path(".cache", "logs")
CPROFILE_PATH = get_full_path(".cache", "cprofile")
PROFILE_DUMP_NAME = "profile_dump"

VPRJ_CONFIG_PATH = get_full_path("vprj_config.json")

PLATFORM_PLUGIN_PATH = get_full_path("custom")
PLATFORM_ROOT_PATH = os.path.dirname(get_full_path())

NEW_PROJECT_DIR = get_full_path("new_project_base")
DEFAULT_KEYWORD = "demo"

VPRJCORE_PLUGIN_PATH = get_full_path()

def dependency(depend_list):
    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            log.debug("depend list = %s" % (depend_list))
            project = args[1]
            for depend_one in depend_list:
                for plugin in project.plugin_list:
                    log.debug("module name = %s" % plugin.module_name)
                    if plugin.module_name == depend_one:
                        index, operate = func.__name__.split(
                            sep="_", maxsplit=1)
                        if operate in plugin.operate_list:
                            if index in plugin.operate_list[operate]:
                                if plugin.operate_list[operate][index](project):
                                    del plugin.operate_list[operate][index]
                                else:
                                    log.debug("'%s' operate failed" %
                                              depend_one)
                                    return False
                            else:
                                log.warning(
                                    "The plugin does not have the attr:'%s'" % func.__name__)
                        else:
                            log.warning(
                                "The plugin does not have the attr:'%s'" % func.__name__)

            return func(*args, **kwargs)

        return wrapper

    return decorate

def get_filename(prefix, suffix, path):
    path = get_full_path(path)
    if not os.path.exists(path):
        os.makedirs(path)
    date_str = time.strftime('%Y%m%d_%H%M%S')
    return os.path.join(path, ''.join((prefix, date_str, suffix)))

def organize_files(path, prefix):
    if os.path.exists(path):
        file_list = os.listdir(path)
        for file in file_list:
            file_fullpath = get_full_path(path, file)
            if os.path.isfile(file_fullpath):
                log_data = file.split("_")[1]
                log_dir = get_full_path(path, prefix + log_data)
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                dest_file = os.path.join(log_dir, os.path.basename(file_fullpath))
                if os.path.exists(dest_file):
                    os.remove(dest_file)
                shutil.move(file_fullpath, log_dir)

def list_file_path(module_path, max_depth=0xff, cur_depth=0, list_dir=False, only_dir=False):
    cur_depth += 1
    module_path = get_full_path(module_path)
    for filename in os.listdir(module_path):
        filename = get_full_path(module_path, filename)
        if os.path.isdir(filename):
            if cur_depth < max_depth:
                for subdir_filename in list_file_path(filename, max_depth, cur_depth, list_dir, only_dir):
                    yield subdir_filename
            if list_dir or only_dir:
                yield filename
        elif not only_dir:
            yield filename

def load_module(module_path, max_depth):
    module_list = []
    module_path = get_full_path(module_path)
    log.debug("module path = '%s'" % module_path)
    if not os.path.exists(module_path):
        log.warning("the module_path '%s' is not exits" % module_path)
        return None
    for filepath in list_file_path(module_path, max_depth):
        filename = os.path.basename(filepath)
        if not filename.endswith(".py") or filename.startswith("_"):
            continue
        module_name = os.path.splitext(filename)[0]
        start_index = filepath.find("project-manager")
        end_index = filepath.find(".py")
        package_name = filepath[start_index:end_index].replace(os.sep, ".")
        import_module = __import__(package_name, fromlist=[module_name])
        if hasattr(import_module, "get_module"):
            module = import_module.get_module()
            module.file_path = import_module.__file__
            module.module_name = module_name
            module.package_name = package_name
            if register_module(module):
                module_list.append(module)
    return module_list

def register_module(module):
    module.operate_list = {}
    attrlist = dir(module)
    for attr in attrlist:
        if not attr.startswith("_"):
            funcattrs = getattr(module, attr)
            if callable(funcattrs):
                if attr.count("_") > 1:
                    index, operate = attr.split(sep="_", maxsplit=1)
                    if operate not in module.operate_list.keys():
                        module.operate_list[operate] = {}
                    module.operate_list[operate][index] = funcattrs
                else:
                    module.operate_list[attr] = funcattrs
    if module.operate_list:
        log.debug("module module_name = %s" % module.module_name)
        log.debug("module package_name = %s" % module.package_name)
        log.debug("module file_path = '%s'" % module.file_path)
        log.debug("module operate_list = %s" % module.operate_list)
        log.debug("register '%s' successfully!" % module.module_name)
        return True
    else:
        log.warning("No matching function in '%s'" % module.module_name)
        return False

class LogManager(object):
    __instance = None
    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance
    def __init__(self):
        self.logger = self._init_logger()
        organize_files(LOG_PATH, "LOG_")
    @staticmethod
    def _init_logger():
        config = {
            'version': 1.0,
            'formatters': {
                'console_formatter': {
                    'format': '[%(asctime)s] [%(levelname)-10s]\t%(message)s',
                },
                'file_formatter': {
                    'format': '[%(asctime)s] [%(levelname)-10s] [%(filename)-20s] [%(funcName)-20s] [%(lineno)-5d]\t%(message)s',
                },
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'level': 'INFO',
                    'formatter': 'console_formatter'
                },
                'file': {
                    'class': 'logging.FileHandler',
                    'filename': get_filename("Log_", ".log", LOG_PATH),
                    'level': 'DEBUG',
                    'mode': 'w',
                    'formatter': 'file_formatter',
                    'encoding': 'utf8',
                    'delay': 'True',
                },
                'file_base_time': {
                    'class': 'logging.handlers.TimedRotatingFileHandler',
                    'filename': 'Log.log',
                    'level': 'DEBUG',
                    'formatter': 'file_formatter',
                    'encoding': 'utf8',
                    'delay': 'True',
                },
            },
            'loggers': {
                'StreamLogger': {
                    'handlers': ['console'],
                    'level': 'DEBUG',
                },
                'FileLogger': {
                    'handlers': ['console', 'file'],
                    'level': 'DEBUG',
                },
            }
        }
        logging.config.dictConfig(config)
        return logging.getLogger("FileLogger")
    def get_logger(self):
        return self.logger

log = LogManager().get_logger()

def func_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(func.__name__, 'took', end - start, 'seconds')
        return result
    return wrapper

def func_cprofile(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        profile = cProfile.Profile()
        try:
            profile.enable()
            result = func(*args, **kwargs)
            profile.disable()
            return result
        finally:
            try:
                organize_files(CPROFILE_PATH, "CPROFILE_")
                profile.dump_stats(PROFILE_DUMP_NAME)
                with open(get_filename("Stats_", ".cprofile", CPROFILE_PATH), "w") as file_steam:
                    ps = pstats.Stats(PROFILE_DUMP_NAME, stream=file_steam)
                    ps.sort_stats("time").print_stats()
                    if os.path.exists(PROFILE_DUMP_NAME):
                        os.remove(PROFILE_DUMP_NAME)
            except:
                if os.path.exists(PROFILE_DUMP_NAME):
                    os.remove(PROFILE_DUMP_NAME)
                log.exception("fail to dump profile")
    return wrapper

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


if __name__ == '__main__':
    main()
