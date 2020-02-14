<!--
 * @Author: WangGuanran
 * @Email: wangguanran@vanzotec.com
 * @Date: 2020-02-14 16:16:32
 * @LastEditTime : 2020-02-14 17:23:23
 * @LastEditors  : WangGuanran
 * @Description: Project_Manager 类设计思路
 * @FilePath: \vprojects\Project_Manger.md
 -->

# Project_Manager 设计思路

## 功能列表

* 新建项目  
    1. 主板项目新建
    2. 客户项目新建
* 删除项目
* 编译项目
    1. 服务器版本编译
    2. 本地环境编译

***

### 新建项目

#### project_manager.py

* -b name 指定主板项目名，不加-b参数代表客户项目
* --server=ServerIP 指定执行该操作的服务器IP，未指定则为本地创建，指定为auto则自动查询服务器状态并分配新建任务
* --build_confirm=yes 指定新建项目需要编译确认，默认不编译，仅保存相关信息
* --base=name 指定项目新建参考的模板项目
* --platform=XXX 指定新建项目的平台
* --android_version=zz 指定新建项目的Android版本

1. ./projeect_manager.py -b AAA # 新建一个主板项目AAA，未指定base，采用默认common
2. ./project_manager.py -b AAA --base=BBB # 新建一个主板项目AAA，以项目BBB为模板创建
3. ./project_manager.py AAA # 新建一个客户项目AAA，新建客户项目时--base参数无效

流程  
1、连接数据库

* 查询该指定名是否重复（重复则返回已有项目参数）
* 查询是否含有--base参数指定的主板名（没有则返回错误）
* 获取base指定主板名的相关信息(例：平台MTK/MT6735)
* 替换名称插入数据库

3、本地创建项目所需要的文件

* 根据新建项目所在平台（MTK/SPRD/RK）动态加载相关模块（mtk_manager.py/sprd_manager.py/rk_magager.py）(传入参数：项目名、项目平台)（返回操作句柄）
* Kernel部分 新建dts/dws/defconfig(MTK)
* Lk,Pl部分 拷贝相关文件，替换相关目录名
* Device目录下 拷贝.mk等配置信息，替换目录名

4、打入Patch、Overidde文件  
5、编译该主板项目，保存仓库内各个目录下最后一笔提交  

查询服务器状态  
分发新建命令至服务器（未指定-s参数时查询服务器状态自动分配）  
