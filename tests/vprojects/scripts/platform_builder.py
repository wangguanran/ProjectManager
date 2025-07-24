"""
PlatformBuilder module for platform-specific project build logic.
"""

from src.log_manager import log
from src.plugins.project_builder import ProjectBuilder


class PlatformBuilder(ProjectBuilder):
    """
    Platform-specific project builder, extends ProjectBuilder.
    """

    def __init__(self):
        # Explicitly implement __init__ to satisfy abstract-method check
        pass

    @staticmethod
    def project_diff(env, projects_info, project_name):
        log.info("[PlatformBuilder] project_diff called")
        return ProjectBuilder.project_diff(env, projects_info, project_name)

    @staticmethod
    def project_pre_build(env, projects_info, project_name):
        log.info("[PlatformBuilder] project_pre_build called")
        return ProjectBuilder.project_pre_build(env, projects_info, project_name)

    @staticmethod
    def project_do_build(env, projects_info, project_name):
        log.info("[PlatformBuilder] project_do_build called")
        return ProjectBuilder.project_do_build(env, projects_info, project_name)

    @staticmethod
    def project_post_build(env, projects_info, project_name):
        log.info("[PlatformBuilder] project_post_build called")
        return ProjectBuilder.project_post_build(env, projects_info, project_name)

    @staticmethod
    def project_build(env, projects_info, project_name):
        log.info("[PlatformBuilder] project_build called")
        return ProjectBuilder.project_build(env, projects_info, project_name)
