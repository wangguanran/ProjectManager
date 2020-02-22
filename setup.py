'''
@Author: WangGuanran
@Email: wangguanran@vanzotec.com
@Date: 2020-02-22 21:39:26
@LastEditTime: 2020-02-22 22:00:36
@LastEditors: WangGuanran
@Description: py setup file
@FilePath: \vprojects\setup.py
'''
from setuptools import setup

setup(
    name='vprojects',
    version='0.01',
    packages=['vprjcore', 'vprjcore.platform'],
    url='https://github.com/wgr191029260/vprojects',
    license='GNU General Public License v3.0',
    author='WangGuanran',
    author_email='wangguanran@vanzotec.com',
    description='For Android Projects'
)
