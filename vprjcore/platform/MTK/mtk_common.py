'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 22:36:07
@LastEditTime: 2020-02-20 00:42:41
@LastEditors: WangGuanran
@Description: Mtk Common Operate py file
@FilePath: \vprojects\vprjcore\platform\MTK\mtk_common.py
'''

from vprjcore.log import log


class MTKCommon(object):

    def __init__(self):
        self.support_list = [
            "MT6735",
            "MT6739",
        ]

    def new_project(self, *args,**kwargs):
        log.debug("In!")
        log.debug(args[0])
        pass

    def del_project(self, *args,**kwargs):
        log.debug("In!")
        pass

    def compile_project(self, *args,**kwargs):
        log.debug("In!")
        pass


# All platform scripts must contain this interface
def get_platform():
    return MTKCommon()
