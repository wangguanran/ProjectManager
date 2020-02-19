'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-16 00:35:02
@LastEditTime: 2020-02-20 00:41:07
@LastEditors: WangGuanran
@Description: common py file
@FilePath: \vprojects\vprjcore\common.py
'''
import os
import time

def _get_filename(preffix, suffix, path):
    '''
    return file name based on time
    '''
    if(not os.path.exists(path)):
        os.makedirs(path)
    date_str = time.strftime('%Y%m%d_%H%M%S')
    return os.path.join(path, ''.join((preffix, date_str, suffix)))
