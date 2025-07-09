"""
Project management utility class for CLI operations.
"""

from src.profiler import auto_profile


@auto_profile
class ProjectManager:
    """
    Project management utility class. All methods are static and stateless.
    """

    def __init__(self):
        raise NotImplementedError(
            "ProjectManager is a utility class and cannot be instantiated."
        )

    @staticmethod
    def project_new(env, projects_info, project_name):
        """
        Create a new project.
        Args:
            env (dict): Global environment dict.
            projects_info (dict): All projects info.
            project_name (str): Project name.
        """
        # TODO: implement project_new

    @staticmethod
    def project_del(env, projects_info, project_name):
        """
        Delete the specified project directory and update its status in the config file.
        Args:
            env (dict): Global environment dict.
            projects_info (dict): All projects info.
            project_name (str): Project name.
        """
        # TODO: implement project_del

    @staticmethod
    def project_build(env, projects_info, project_name):
        """
        Build the specified project.
        Args:
            env (dict): Global environment dict.
            projects_info (dict): All projects info.
            project_name (str): Project name.
        """
        # TODO: implement project_build

    @staticmethod
    def board_new(env, projects_info, board_name):
        """
        Create a new board.
        Args:
            env (dict): Global environment dict.
            projects_info (dict): All projects info.
            board_name (str): Board name.
        """
        # TODO: implement board_new

    @staticmethod
    def board_del(env, projects_info, board_name):
        """
        Delete the specified board.
        Args:
            env (dict): Global environment dict.
            projects_info (dict): All projects info.
            board_name (str): Board name.
        """
        # TODO: implement board_del
