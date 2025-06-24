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

from .common import func_cprofile, log, get_full_path, list_file_path
from .common import PLATFORM_ROOT_PATH, PROJECT_INFO_PATH, VPRJCORE_VERSION, VPRJCORE_PLUGIN_PATH

DEFAULT_KEYWORD = "demo"


class Project(object):

    def __init__(self, args_dict: dict):
        operate = args_dict.pop("operate").lower()
        # is_inner = args_dict.pop("is_inner")
        self.name = args_dict.pop("project_name").lower()
        # self.is_board = args_dict.pop("is_board")
        self.base = args_dict.pop("base").lower()

        self.platform = self._get_platform_name()
        op_handler = self._get_op_handler()

        self.executed(operate, op_handler)

    @func_cprofile
    def executed(self, operate, op_handler):
        if operate in op_handler.keys():
            if op_handler[operate](self):
                self._update_platform_json_file()
                log.info("Operation succeeded!")
            else:
                log.info("Operation failed!")
        else:
            log.warning("Can not support this operate")

    def new_platform(self):
        file_list = []
        link_list = {}
        platform_info = OrderedDict()

        if os.path.basename(os.getcwd()) in ["vprojects", "vprjcore"]:
            log.error("This command cannot be executed in the current directory")
            return False

        platform = self.platform
        platform_dir_path = get_full_path(platform)
        if not os.path.exists(platform_dir_path):
            os.makedirs(platform_dir_path)
        else:
            log.warning("The platform is already exists!")
            return False
        platform_info["platform"] = platform.upper()

        create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        platform_info["create_time"] = create_time

        log.debug("platform root path = %s" % PLATFORM_ROOT_PATH)
        for dirname in list_file_path(PLATFORM_ROOT_PATH, max_depth=1, only_dir=True):
            if os.path.basename(dirname) in ["vprojects", "zprojects"]:
                continue
            try:
                repo = git.Repo(dirname)
                untracked_files_list = repo.untracked_files
                if len(untracked_files_list) == 0:
                    continue
                for file_name in untracked_files_list:
                    src = os.path.join(
                        os.path.basename(dirname), file_name)
                    if os.path.islink(src):
                        soft_link_path = os.readlink(src)
                        log.debug("link='%s',file name='%s'" % (
                            soft_link_path, file_name))
                        link_list[src] = soft_link_path
                    else:
                        dest = os.path.join(
                            platform_dir_path, os.path.dirname(src))
                        log.debug("src='%s' dest='%s'" % (src, dest))
                        if not os.path.exists(dest):
                            os.makedirs(dest)
                        shutil.copy(src, dest)
                        file_list.append(src)
            except git.exc.InvalidGitRepositoryError:
                continue

        platform_info["link_list"] = link_list
        platform_info["file_list"] = file_list
        json_file_path = get_full_path(platform, platform+".json")
        with open(json_file_path, "w+") as f_write:
            json.dump(platform_info, f_write, indent=4)

        return True

    def new_project(self):
        keyword = DEFAULT_KEYWORD
        basedir = get_full_path(self.base)
        destdir = get_full_path(self.name)
        log.debug("basedir = '%s' destdir = '%s'" % (basedir, destdir))

        if os.path.exists(basedir):
            if os.path.exists(destdir):
                log.error(
                    "The project has been created and cannot be created repeatedly")
            else:
                with open(PROJECT_INFO_PATH, "r") as f_read:
                    platform_json_info = {}
                    platform_json_info = json.load(f_read)
                    if hasattr(platform_json_info[self.base], "keyword"):
                        keyword = platform_json_info[self.base]["keyword"]
                    else:
                        if self.base.upper() == self.platform.upper():
                            keyword = DEFAULT_KEYWORD
                        else:
                            keyword = self.base
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
                                    line = line.replace(keyword, self.name)
                                    f_rw.write(line)
                        except:
                            log.error("Can not read file '%s'" % file_path)
                            return False
                    if keyword in os.path.basename(file_path):
                        p_dest = os.path.join(os.path.dirname(
                            file_path), os.path.basename(file_path).replace(keyword, self.name))
                        log.debug(
                            "rename src file = '%s' dest file = '%s'" % (file_path, p_dest))
                        os.rename(file_path, p_dest)
                return True
        else:
            log.error("No platform file, unable to create new project")

        return False

    def del_project(self):
        log.debug("In!")

        json_info = {}
        project_path = get_full_path(self.name)
        log.debug("project path = %s" % project_path)

        if os.path.exists(project_path):
            shutil.rmtree(project_path)
        else:
            log.warning("The '%s' path is already delete" % self.name)
        try:
            with open(self.info_path, "r") as f_read:
                json_info = json.load(f_read)
                json_info[self.name]["status"] = "deleted"
            with open(self.info_path, "w+") as f_write:
                json.dump(json_info, f_write, indent=4)
        except:
            log.exception("Can not find info file")
            return False

        return True

    def _get_platform_name(self):
        platform = None

        try:
            json_info = json.load(open(PROJECT_INFO_PATH, "r"))
            if self.name in json_info.keys():
                platform = json_info[self.name]["platform"]
            elif self.base in json_info.keys():
                platform = json_info[self.base]["platform"]
            else:
                log.debug("the project's platform is null,return self.name")
                return self.name
        except FileNotFoundError:
            log.exception("'%s' does not exists" % PROJECT_INFO_PATH)

        return platform

    def _update_platform_json_file(self, status="normal"):
        json_info_ordered = OrderedDict()
        prj_info = OrderedDict()
        json_info = {}
        try:
            json_info = json.load(open(PROJECT_INFO_PATH, "r"))
        except:
            log.debug("%s is null" % PROJECT_INFO_PATH)

        if self.name in json_info.keys():
            if json_info[self.name]["status"] == status:
                return True

        prj_info["platform"] = self.platform.upper()
        prj_info["create_time"] = datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S")
        prj_info["base"] = self.base
        prj_info["status"] = "normal"

        json_info[self.name] = prj_info
        prj_list = sorted(json_info.keys())
        for info in prj_list:
            json_info_ordered[info] = json_info[info]
        json.dump(json_info_ordered, open(PROJECT_INFO_PATH, "w+"), indent=4)

        return True

    def _get_op_handler(self):
        op_handler = {}
        module = None

        if self.platform is None:
            log.error("The platform is None,please check the project's name")
            return None

        # Scan module info
        for dir_path in list_file_path(VPRJCORE_PLUGIN_PATH, only_dir=True):
            for file_path in list_file_path(dir_path):
                if not file_path.endswith(".py"):
                    continue
                log.debug("file_path=%s" % file_path)
                name = os.path.basename(file_path).split(sep=".")[0]
                start_index = file_path.find("vprjcore")
                end_index = file_path.find(".py")
                package = file_path[start_index:end_index].replace(
                    os.sep, ".")
                log.debug("name=%s,package=%s" % (name, package))
                import_module = __import__(package, fromlist=[name])
                if hasattr(import_module, "get_platform"):
                    temp = import_module.get_platform()
                    if hasattr(temp, "support_list"):
                        if self.platform in temp.support_list:
                            module = temp
                            break

        if module:
            for attr in dir(module):
                if attr.startswith("_"):
                    continue
                funcattrs = getattr(module, attr)
                if callable(funcattrs):
                    op_handler[attr] = funcattrs
            return op_handler
        else:
            return None


def parse_cmd():
    """
    @description: Parsing command line parameters
    @param {type} None
    @return: arg list(dict)
    """
    log.debug("argv = %s" % sys.argv)
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', action="version",
                        version=VPRJCORE_VERSION)

    parser.add_argument("operate", help="supported operations")
    parser.add_argument("project_name", help="project name")

    # parser.add_argument('-b', action="store_true", dest="is_board",
    #                     help="specify the new project as the board project", default=False)
    # parser.add_argument('-i', action="store_true", dest="is_inner",
    #                     help="specify this operation as an internal instruction", default=False)
    parser.add_argument(
        "--base", help="specify a new project to be created based on this", default="None")

    args = parser.parse_args()
    # log.info(args.__dict__)
    return args.__dict__


def main():
    args_dict = parse_cmd()
    project = Project(args_dict)


if __name__ == "__main__":
    main()
