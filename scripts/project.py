'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 16:35:40
@LastEditTime: 2020-02-16 16:35:41
@LastEditors: WangGuanran
@Description: project py file
@FilePath: \vprojects\scripts\project.py
'''

from scripts.plugins.po import PO
from scripts.log import log


class Project(object):

    def __init__(self, prj_info):
        log.debug("In!")
        self.prj_info = prj_info
        # self.project_name = prj_info['name']
        # self.platform = prj_info['platform']
        # self.kernel_version = prj_info['kernel_version']
        # self.android_version = prj_info['android_version']

        self.support_platform = self._scan_platform()
        self.patch_override = PO()

    def _scan_platform(self):
        log.debug("In!")
        pass

    def dispatch(self, operate, info):
        log.debug("In!")
        return self.op_hander[operate].values(info)

    def _new_project(self):
        log.debug("In!")
        # TODO 本地创建项目所需要的文件
        # * 根据新建项目所在平台（MTK/SPRD/RK）动态加载相关模块（mtk/sprd/rk_manager.py）(传入参数：项目名、项目平台)（返回操作句柄）
        # * Kernel部分 新建dts/dws/defconfig(MTK)
        # * Lk, Pl部分 拷贝相关文件，替换相关目录名
        # * Device目录下 拷贝.mk等配置信息，替换目录名
        pass

    def _new_board(self):
        log.debug("In!")
        pass

    def _del_project(self):
        log.debug("In!")
        pass

    def _compile_project(self):
        log.debug("In!")
        pass
