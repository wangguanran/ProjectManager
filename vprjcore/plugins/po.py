'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 17:18:01
@LastEditTime: 2020-02-20 14:10:19
@LastEditors: WangGuanran
@Description: patch override py file
@FilePath: \vprojects\vprjcore\plugins\po.py
'''
from vprjcore.log import log


class PO(object):
    def __init__(self):
        self.support_list = [
            "MT6735"
        ]
        self.unsupported_list = [
            ""
        ]
        pass

    def before_new_project(self, project):
        log.debug("In!")
        pass

    def before_compile(self, project):
        log.debug("In!")
        pass

    def after_compile(self, project):
        log.debug("In!")
        pass

# All plugin must contain this interface


def get_plugin_object():
    return PO()
