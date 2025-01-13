
# vprojects

Android项目管理

## 已完成

### projects.py

#### 操作指令

```txt
usage: project.py [-h] [-v] [-b] [--base BASE] operate project_name

positional arguments:
  operate        supported operations
  project_name   project name

optional arguments:
  -h, --help     show this help message and exit
  -v, --version  show program's version number and exit

new_project:
  -b             specify the new project as the board project
  --base BASE    specify a new project to be created based on this
```

1.脚本可以同时在代码根目录，vprojects目录，vprjcore目录下运行  
2.代码执行时会在vprojects下创建.cache/logs和.cache/cprofile目录，保存名会包含当前时间

* logs目录下保存脚本的运行log

```log
vprojects/.cache/logs/Log_20200225_223744.log

[2020-02-25 22:37:44,542] [DEBUG     ] [project.py          ] [parse_cmd           ] [111  ]	argv = ['/home/dserver/build_projects2/build2/VZ6737M_65_I_N_vtrunk/vprojects/vprjcore/project.py', 'del_project', 'tnz801']
```

* cprofile目录下保存代码的执行时间分析

```txt
vprojects/.cache/cprofile/Stats_20200225_223744.cprofile

Tue Feb 25 22:37:44 2020    profile_dump

         4066 function calls (3948 primitive calls) in 0.023 seconds

   Ordered by: internal time

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      214    0.007    0.000    0.007    0.000 {built-in method unlink}
     95/1    0.003    0.000    0.020    0.020 /usr/lib/python3.4/shutil.py:380(_rmtree_safe_fd)
      309    0.002    0.000    0.002    0.000 {built-in method stat}
      309    0.001    0.000    0.003    0.000 /usr/lib/python3.4/posixpath.py:70(join)
       95    0.001    0.000    0.001    0.000 {built-in method listdir}
       95    0.001    0.000    0.001    0.000 {built-in method close}
       95    0.001    0.000    0.001    0.000 {built-in method rmdir}
      322    0.001    0.000    0.001    0.000 /usr/lib/python3.4/posixpath.py:38(_get_sep)
      373    0.000    0.000    0.000    0.000 {built-in method isinstance}

```

#### 新建主板项目

* 以平台文件为base创建项目
* 以其他主板项目为base创建项目

### platform_manager.py

#### 构建平台项目

* 自动扫描代码根目录下的所有目录，记录各目录下Git未追踪的文件
* 保存文件完整路径名，以及软连接文件链接地址
* 记录平台项目的创建时间
* 将新增的项目文件拷贝至vprojects中
* 手动输入平台名称，如：mt6735，脚本会在vprojects/new_project_base目录中创建对应的目录，将所有新增文件拷贝到此目录下
* 记录的数据有[^keyword]，create_time,file_list,link_list

```json
vprojects/new_project_base/new_project_base.json
{
    "mt6735": {
        "keyword":"demo",
        "create_time": "2020-02-25 21:13:31",
        "file_list": [
            "kernel-3.18/arch/arm/boot/dts/demo.dts",
            "..."
        ],
        "link_list": {
            "vendor/mediatek/proprietary/bootable/bootloader/lk/target/demo/dct": "../../../../../../../../kernel-3.18/drivers/misc/mediatek/mach/mt6735/demo/dct",
            "...":"..."
        }
    }
}

```

# 计划添加

1.po_manager.py add_to_po,new_po --common,del_po,list_po,cmp_po_diff
2.自动保存patch文件时，添加注释信息，注释信息包括修改时间、修改人、邮件、修改日志。相关信息可以从git中读取

[^keyword]:keyword在创建json文件时并不会主动生成，默认此值为"demo",是指明在以此平台为模板创建主板项目时，脚本会对文件名中出现的哪个字符串左替换操作
