# vprojects

Universal Project Management Tool

## Completed

### projects.py

#### Operation Commands

```txt
usage: project.py [-h] [-v] [-b] [--base BASE] operate project_name

positional arguments:
  operate        supported operations
  project_name   project name

optional arguments:
  -h, --help     show this help message and exit
  -v, --version  show program's version number and exit

project_new:
  -b             specify the new project as the board project
  --base BASE    specify a new project to be created based on this
```

1. When code is executed, it will create .cache/logs and .cache/cprofile directories under vprojects, with filenames containing the current time

* The logs directory stores script execution logs

```log
vprojects/.cache/logs/Log_20200225_223744.log

[2020-02-25 22:37:44,542] [DEBUG     ] [project.py          ] [parse_cmd           ] [111  ]	argv = ['/home/dserver/build_projects2/build2/VZ6737M_65_I_N_vtrunk/vprojects/project-manager/project.py', 'project_del', 'tnz801']
```

* The cprofile directory stores code execution time analysis

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

#### Create New Board Project

* Create project based on platform files
* Create project based on other board projects

### platform_manager.py

#### Build Platform Project

* Automatically scan all directories under the code root directory, record Git untracked files in each directory
* Save complete file path names and soft link file link addresses
* Record platform project creation time
* Copy new project files to vprojects
* Manually input platform name, such as: mt6735, the script will create corresponding directories in vprojects/new_project_base directory, and copy all new files to this directory
* Recorded data includes [^keyword], create_time, file_list, link_list

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

# Planned Additions

1. po_manager.py add_to_po, new_po --common, del_po, list_po, cmp_po_diff
2. When automatically saving patch files, add comment information including modification time, modifier, email, and modification log. Related information can be read from git

[^keyword]: keyword is not actively generated when creating json files, default value is "demo", which specifies which string in the filename the script will perform replacement operations on when creating board projects based on this platform as a template
