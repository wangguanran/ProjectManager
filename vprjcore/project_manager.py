'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-21 11:03:15
@LastEditTime: 2020-02-25 21:28:10
@LastEditors: WangGuanran
@Description: Project manager py file
@FilePath: /vprojects/vprjcore/project_manager.py
'''
import os
import sys
import json
import shutil
import collections

from vprjcore.common import log, list_file_path, get_full_path

BOARD_INFO_PATH = get_full_path("board_info.json")
PROJECT_INFO_PATH = get_full_path("project_info.json")


class ProjectManager(object):

    """
    Singleton mode
    """
    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self):
        super().__init__()

    def before_new_project(self, project):
        project.by_new_project_base = False
        base_name = project.args_dict.pop("base", None)
        if base_name is None:
            log.error("You need to use '--base' to specify platform information")
            return False
        else:
            project.base_name = base_name
        log.debug("base name = %s" % base_name)
        if project.args_dict["is_board"]:
            self.info_path = BOARD_INFO_PATH
        else:
            self.info_path = PROJECT_INFO_PATH
        log.debug("info path = '%s'" % self.info_path)

        for dir_name in list_file_path("new_project_base", max_depth=1, only_dir=True):
            if os.path.basename(dir_name).upper() == base_name.upper():
                project.platform_name = base_name.upper()
                project.by_new_project_base = True
                log.debug("get the platform in new_project_base")
                # platform_path = get_full_path(
                #     "new_project_base", project.platform_name)
                # log.debug("platform path = %s" % platform_path)
                # if os.path.exists(self.info_path):
                #     json_info = json.load(open(self.info_path, "r"))
                #     if project.platform_name in json_info.keys():
                #         if "ignore_list" in json_info[project.platform_name]:
                #             ignore_list = json_info[project.platform_name].ignore_list
                #             log.debug("platform '%s' ignore list = %s" %
                #                       (project.platform_name, ignore_list))
                #             ignore_dir = os.path.join(platform_path, "ignore")
                #             if os.path.exists(ignore_list):
                #                 os.makedirs(ignore_dir)
                #             for ignore_one in ignore_list:
                #                 ignore_path = os.path.join(
                #                     platform_path, ignore_one)
                #                 log.debug("move ignore file '%s'" %
                #                           ignore_path)
                #                 shutil.move(ignore_path, ignore_dir)
                #     else:
                #         log.warning("the platform info is none")
                # else:
                #     log.warning("board info '%s' is null")

                return True

        json_info = json.load(open(self.info_path, "r"))
        for prj_name, temp_info in json_info.items():
            if prj_name == base_name:
                project.platform_name = temp_info["platform_name"]
                log.debug("get the platform in project_info.json")
                return True

        log.debug("Get the platform failed")
        return False

    def after_new_project(self, project):
        log.debug("In!")
        # save project info
        prj_info = {}
        temp_json_info = {}
        json_info = collections.OrderedDict()
        except_list = [
            "args_dict",
            "platform_handler",
            "plugin_list",
            "operate",
        ]
        try:
            temp_json_info = json.load(open(self.info_path, "r"))
        except:
            log.debug("%s is null" % self.info_path)

        for attr in dir(project):
            var = getattr(project, attr)
            if not (callable(var) or attr.startswith("_") or attr in except_list):
                prj_info[attr] = var
        temp_json_info[project.project_name] = prj_info
        prj_list = sorted(temp_json_info.keys())
        for info in prj_list:
            json_info[info] = temp_json_info[info]
        json.dump(json_info, open(self.info_path, "w+"), indent=4)

        return True

    def before_compile_project(self, project_name):
        """
        @description: get project information from cache file or db
        @param {type} project_name:project name(str)
        @return: project info(dict)
        """
        prj_info = None

        # TODO Query the database to confirm whether the project data is updated
        # If yes, update the cache file. If no project information is found, an error will be returned
        log.debug("query database")
        # Save project info into cache(PROJECT_INFO_PATH)
        # with open(PROJECT_INFO_PATH, "w+") as f_write:
        #     json.dump(prj_info, f_write)
        #     f_write.write("\n")
        # END

        # Search project info in PROJECT_INFO_PATH first
        if os.path.exists(PROJECT_INFO_PATH):
            json_info = json.load(open(PROJECT_INFO_PATH, "r"))
            for prj_name, temp_info in json_info.items():
                if prj_name.lower() == project_name.lower():
                    prj_info = temp_info

        if prj_info is None:
            log.warning("The project('%s') info is None" % project_name)
        else:
            prj_info["name"] = project_name.lower()
            log.info("prj_info = %s" % prj_info)
        return prj_info


def get_module():
    return ProjectManager()
