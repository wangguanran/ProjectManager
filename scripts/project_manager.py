'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-14 20:01:07
@LastEditTime: 2020-02-15 21:30:21
@LastEditors: WangGuanran
@Description: project_manager py file
@FilePath: \vprojects\scripts\project_manager.py
'''

import sys
import time

from operate_database import Operate_Database
from log import log


class Project_Manager(object):

    def __init__(self):
        log.debug("Project_Manager __init__ Im In")

    "print Project_Manager help"
    @staticmethod
    def print_help():
        log.info("\t -b name              指定主板项目名，不加-b参数代表客户项目")
        log.info(
            "\t --server=ServerIP    指定执行该操作的服务器IP，未指定则为本地创建，指定为auto则自动查询服务器状态并分配新建任务")
        log.info("\t --build_confirm=yes  指定新建项目需要编译确认，默认为no不编译，仅保存相关信息")
        log.info("\t --base=name          指定项目新建参考的模板项目")
        log.info("\t --platform=XXX       指定新建项目的平台")
        log.info("\t --android_version=zz 指定新建项目的Android版本")

    "Project_Manager Main"
    @staticmethod
    def main(self):
        log.debug("In!")
        # TODO 连接数据库
        op_db_handler = Operate_Database()
        # * 查询该指定名是否重复（重复则返回已有项目参数）
        # * 查询是否含有--base参数指定的主板名（没有则返回错误）
        # * 获取base指定主板名的相关信息(例：平台MTK/MT6735)
        # * 替换名称插入数据库
        # TODO 本地创建项目所需要的文件
        # * 根据新建项目所在平台（MTK/SPRD/RK）动态加载相关模块（mtk/sprd/rk_manager.py）(传入参数：项目名、项目平台)（返回操作句柄）
        # * Kernel部分 新建dts/dws/defconfig(MTK)
        # * Lk, Pl部分 拷贝相关文件，替换相关目录名
        # * Device目录下 拷贝.mk等配置信息，替换目录名
        # TODO 打入Patch、Override文件
        # TODO 编译该主板项目，保存仓库内各个目录下最后一笔提交

        # 查询服务器状态
        # 分发新建命令至服务器（未指定-s参数时查询服务器状态自动分配）
        pass


if __name__ == "__main__":
    argc = len(sys.argv)
    log.debug("lens = %d,argv = %s" % (argc, sys.argv))
    if argc <= 1:
        log.error("argc <= 1")
        Project_Manager.print_help()
    else:
        log.debug("process Project_Manager.main")
        Project_Manager.main(sys.argv)
