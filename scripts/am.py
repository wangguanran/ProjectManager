'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-23 14:06:25
@LastEditTime: 2020-02-23 14:29:41
@LastEditors: WangGuanran
@Description: For all command
@FilePath: \vprojects\scripts\am.py
'''

import os
import sys

if __name__ == "__main__":
    if os.path.basename(os.getcwd()) == "vprojects":
        sys.path.append(os.getcwd())
    elif os.path.basename(os.getcwd()) in ["vprjcore","scripts"]:
        sys.path.append(os.path.dirname(os.getcwd()))
    else:
        sys.path.append(os.path.join(os.getcwd(),"vprojects"))

    from vprjcore.project import parse_cmd,Project
    args_dict = parse_cmd()
    project = Project(args_dict)
