'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 22:36:07
@LastEditTime: 2020-02-16 22:36:08
@LastEditors: WangGuanran
@Description: Mtk Common Operate py file
@FilePath: \vprojects\scripts\platform\MTK\mtk_common.py
'''

from scripts.log import log


class MTKCommon(object):

    def __init__(self):
        self.vendor = "MTK"
        self.support_list = [
            "MT6735",
            "MT6739",
        ]
        self.op_handler = {
            "new_project": self._new_project,
            "new_board": self._new_board,
            "compile_project": self._compile_project,
            "del_project": self._del_project,
        }

    def dispatch(self, args):
        log.debug("operate = %s" % (args["operate"]))
        log.debug("project_name = %s" % (args["project_name"]))
        log.debug("info = %s" % (args["info"]))
        try:
            return self.op_handler[args["operate"]](args["project_name"],args["info"])
        except:
            log.exception("The platform is not support '%s'"%(args["operate"]))
            return None

    def _new_project(self,project_name,info):
        log.debug("In!")
        # TODO 本地创建项目所需要的文件
        # * 根据新建项目所在平台（MTK/SPRD/RK）动态加载相关模块（mtk/sprd/rk_manager.py）(传入参数：项目名、项目平台)（返回操作句柄）
        # * Kernel部分 新建dts/dws/defconfig(MTK)
        # * Lk, Pl部分 拷贝相关文件，替换相关目录名
        # * Device目录下 拷贝.mk等配置信息，替换目录名
        pass

    def _new_board(self,project_name,info):
        log.debug("In!")
        pass

    def _del_project(self,project_name,info):
        log.debug("In!")
        pass

    def _compile_project(self,project_name,info):
        log.debug("In!")
        pass


def register_platform(platform_manager):
    log.debug("In!")
    platform = MTKCommon()
    platform_manager.add_platform(platform)
