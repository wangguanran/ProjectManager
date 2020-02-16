'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 17:18:01
@LastEditTime: 2020-02-16 17:18:01
@LastEditors: WangGuanran
@Description: patch override py file
@FilePath: \vprojects\scripts\po.py
'''
from scripts.log import log


class PO(object):
    def __init__(self):
        log.debug("In!")
        super().__init__()
