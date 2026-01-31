# ProjectManager 测试用例（基于代码逻辑）

## 通用测试数据

### 数据集A：单仓库 + 基础 projects 结构
1. 在临时目录创建工作区并进入，例如：`mkdir -p /tmp/pm_case_a && cd /tmp/pm_case_a`。
2. 复制或克隆 ProjectManager 代码到当前目录，确保可执行 `python -m src`。
3. 在工作区根目录初始化并提交一次 Git（用于 po_apply / project_diff）：
   1) `git init`
   2) `printf "baseline" > baseline.txt`
   3) `git add baseline.txt && git commit -m "init"`
4. 创建基础 projects 目录结构：
   1) `mkdir -p projects/common`
   2) `cat > projects/common/common.ini <<'INI'`
      
      `[common]`
      `PROJECT_PLATFORM = platA`
      `PROJECT_CUSTOMER = custA`
      `PROJECT_PO_CONFIG = po_base`
      
      `[po-po_base]`
      `PROJECT_PO_DIR = custom`
      `PROJECT_PO_FILE_COPY = cfg/*.ini:out/cfg/ \\\n       data/*:out/data/`
      
      `INI`
   3) `mkdir -p projects/boardA`
   4) `cat > projects/boardA/boardA.ini <<'INI'`
      
      `[boardA]`
      `PROJECT_NAME = boardA`
      `PROJECT_PO_CONFIG = po_base`
      
      `[projA]`
      `PROJECT_NAME = projA`
      `PROJECT_PLATFORM = platA`
      `PROJECT_CUSTOMER = custA`
      `PROJECT_PO_CONFIG = po_base po_extra`
      
      `[projA-sub]`
      `PROJECT_NAME = projA_sub`
      `PROJECT_PO_CONFIG = po_sub`
      
      `INI`
   5) `mkdir -p projects/boardA/po/po_base/{patches,overrides,custom/cfg,custom/data}`
   6) `printf "k=v" > projects/boardA/po/po_base/custom/cfg/sample.ini`
   7) `printf "data" > projects/boardA/po/po_base/custom/data/sample.dat`
5. 如需测试覆盖文件或补丁：
   1) 在工作区根目录新建文件 `printf "line1" > src/tmp_file.txt`
   2) 执行 `git add src/tmp_file.txt && git commit -m "add tmp file"`
   3) 修改文件 `printf "line1\nline2" > src/tmp_file.txt`
   4) 生成补丁 `git diff -- src/tmp_file.txt > projects/boardA/po/po_base/patches/tmp_file.patch`
   5) 在 overrides 下准备覆盖文件：`cp src/tmp_file.txt projects/boardA/po/po_base/overrides/`

### 数据集B：manifest 多仓库结构（用于 _find_repositories / project_diff）
1. 新建工作区并进入，例如：`mkdir -p /tmp/pm_case_b && cd /tmp/pm_case_b`。
2. 创建多仓库目录：
   1) `mkdir -p repo1 repo2`
   2) `git -C repo1 init && printf "r1" > repo1/a.txt && git -C repo1 add a.txt && git -C repo1 commit -m "r1"`
   3) `git -C repo2 init && printf "r2" > repo2/b.txt && git -C repo2 add b.txt && git -C repo2 commit -m "r2"`
3. 创建 .repo/manifest.xml：
   1) `mkdir -p .repo/manifests`
   2) `cat > .repo/manifest.xml <<'XML'`
      
      `<manifest>`
      `  <project name="repo1" path="repo1" />`
      `  <project name="repo2" path="repo2" />`
      `</manifest>`
      
      `XML`
4. 在工作区根目录准备一个最小 projects 目录（可复用数据集A的步骤4）。

---

## 1. CLI 与参数解析（src/__main__.py）

| 用例ID | 模块 | 用例名称 | 前置条件 | 步骤 | 预期结果 | 优先级 | 类型 |
|---|---|---|---|---|---|---|---|
| CLI-001 | CLI/参数解析 | `--help` 输出包含操作列表与插件参数说明 | 已完成数据集A | 1. 在工作区根目录执行 `python -m src --help`。<br>2. 查看输出中的 `supported operations` 列表。<br>3. 查看输出中的插件参数说明（如 `--keep-diff-dir` 或 `--short`）。 | 帮助信息包含已注册的操作名称与可用参数；格式对齐，无报错。 | P1 | 功能 |
| CLI-002 | CLI/参数解析 | `--version` 读取 pyproject.toml | 已完成数据集A | 1. 执行 `python -m src --version`。<br>2. 记录输出版本号。<br>3. 打开 `pyproject.toml` 中 `project.version` 对比。 | 版本号与 `pyproject.toml` 中一致；无异常。 | P1 | 功能 |
| CLI-003 | CLI/参数解析 | 精确匹配操作名执行 | 已完成数据集A | 1. 执行 `python -m src po_list projA --short`。<br>2. 观察输出。 | 命令执行成功，输出仅包含 PO 名称；无 “Unknown operation” 报错。 | P0 | 功能 |
| CLI-004 | CLI/参数解析 | 模糊匹配（前缀）自动纠正 | 已完成数据集A | 1. 执行 `python -m src buil projA`。<br>2. 观察控制台提示与日志（或 `.cache/latest.log`）。 | 提示模糊匹配并执行 `project_build`；命令不因未知操作退出。 | P1 | 兼容性 |
| CLI-005 | CLI/参数解析 | 模糊匹配歧义提示 | 已完成数据集A | 1. 执行 `python -m src po projA`。<br>2. 观察控制台输出。 | 控制台提示操作歧义并显示可能选项；选择一个最佳匹配继续执行。 | P2 | 兼容性 |
| CLI-006 | CLI/参数解析 | 未知操作提示建议 | 已完成数据集A | 1. 执行 `python -m src unknown_op projA`。 | 报错提示未知操作，并给出可能的建议或可用操作列表；进程退出码非 0。 | P1 | 异常 |
| CLI-007 | CLI/参数解析 | 解析 `--short` 为布尔参数 | 已完成数据集A | 1. 执行 `python -m src po_list projA --short`。<br>2. 观察输出格式。 | 仅输出 PO 名称，不输出 patch/override 详情。 | P1 | 功能 |
| CLI-008 | CLI/参数解析 | 不支持的参数触发 TypeError | 已完成数据集A | 1. 执行 `python -m src po_list projA --unknown-flag 1`。 | 调用函数时报 `TypeError` 并退出；日志中包含参数错误信息。 | P1 | 异常 |
| CLI-009 | CLI/参数解析 | 缺少必需参数时提示 | 已完成数据集A | 1. 执行 `python -m src project_new`。 | 输出缺少参数错误，提示必需参数列表，退出码非 0。 | P0 | 异常 |

## 2. 配置加载与项目索引（src/__main__.py）

| 用例ID | 模块 | 用例名称 | 前置条件 | 步骤 | 预期结果 | 优先级 | 类型 |
|---|---|---|---|---|---|---|---|
| CFG-001 | 配置加载 | 缺失 common.ini 时降级 | 删除或重命名 `projects/common/common.ini` | 1. 执行任意命令（如 `python -m src po_list projA`）。<br>2. 查看日志。 | 日志提示 common 配置缺失；程序仍可运行，common 配置为空。 | P2 | 兼容性 |
| CFG-002 | 配置加载 | common.ini 支持 [common] 与 [po-*] 分区 | 已完成数据集A | 1. 执行 `python -m src po_list projA`。<br>2. 查看日志中的 `Loaded po configurations` 列表。 | `po-po_base` 被识别并加载到 `po_configs`；`common` 被加载到 common 配置。 | P1 | 功能 |
| CFG-003 | 配置加载 | 行内注释剥离（# 或 ;） | 修改 `projects/common/common.ini` 添加 `KEY = value # comment` | 1. 执行 `python -m src po_list projA`。<br>2. 观察加载到的配置值（可在日志或调试打印中确认）。 | 配置值不包含 `# comment` 或 `; comment`。 | P2 | 功能 |
| CFG-004 | 项目扫描 | projects 目录不存在 | 临时将 `projects` 目录改名 | 1. 运行 `python -m src po_list projA`。 | 日志提示 projects 目录不存在；项目列表为空；命令不崩溃。 | P1 | 异常 |
| CFG-005 | 项目扫描 | board 目录无 ini 文件时跳过 | 在 `projects` 下创建空目录 `boardEmpty/` | 1. 运行 `python -m src po_list projA`。<br>2. 查看日志。 | 日志提示该 board 无 ini 文件；不会写入 projects_info。 | P2 | 兼容性 |
| CFG-006 | 项目扫描 | board 目录存在多个 ini 时断言失败 | 在某个 board 目录放置两个 ini 文件 | 1. 执行 `python -m src po_list projA`。 | 触发断言错误，提示发现多个 ini 文件；进程终止。 | P1 | 异常 |
| CFG-007 | 项目扫描 | 同一 section 内重复 key 触发跳过 | 在 ini 中同一 section 写两次 `PROJECT_NAME` | 1. 运行 `python -m src po_list projA`。<br>2. 查看日志。 | 日志报重复 key；该 board 的项目配置被跳过。 | P1 | 异常 |
| CFG-008 | 配置继承 | common + parent + child 合并与 PO 配置拼接 | 已完成数据集A | 1. 确认 `projA` 与 `projA-sub` 均存在。<br>2. 运行 `python -m src po_list projA-sub`。<br>3. 检查子项目配置中 `PROJECT_PO_CONFIG` 是否包含父级与子级拼接。 | 子项目配置包含 common 与父级配置；`PROJECT_PO_CONFIG` 按空格拼接。 | P1 | 功能 |
| CFG-009 | 项目关系 | parent/children 关系构建 | 已完成数据集A | 1. 在日志或调试输出中查看 `projects_info`。 | `projA-sub` 的 `parent` 为 `projA`；`projA` 的 `children` 包含 `projA-sub`。 | P2 | 功能 |
| CFG-010 | 项目索引写入 | board 目录生成 projects.json | 已完成数据集A | 1. 执行任意命令（如 `python -m src po_list projA`）。<br>2. 检查 `projects/boardA/projects.json`。 | `projects.json` 包含 board_name、last_updated、projects 列表与配置。 | P1 | 功能 |

## 3. 仓库发现与索引（_find_repositories）

| 用例ID | 模块 | 用例名称 | 前置条件 | 步骤 | 预期结果 | 优先级 | 类型 |
|---|---|---|---|---|---|---|---|
| REPO-001 | 仓库发现 | 单仓库场景识别 root | 已完成数据集A | 1. 在工作区执行 `python -m src project_diff projA`。<br>2. 查看 `projects/repositories.json`。 | `repositories` 列表包含 `name=root` 与当前路径；`discovery_type=single`。 | P1 | 功能 |
| REPO-002 | 仓库发现 | manifest 多仓库识别 | 已完成数据集B | 1. 在数据集B根目录执行 `python -m src project_diff projA`。<br>2. 查看 `projects/repositories.json`。 | `repositories` 列表包含 manifest 中的项目路径；`discovery_type=manifest`。 | P1 | 功能 |
| REPO-003 | 仓库发现 | manifest include 丢失提示 | 在 manifest 中添加 `<include name="missing.xml"/>` | 1. 执行 `python -m src project_diff projA`。<br>2. 查看日志。 | 日志提示 include 文件未找到；其他仓库仍可被识别。 | P2 | 兼容性 |
| REPO-004 | 仓库发现 | 无 .repo 且无 .git | 在无 Git 初始化的新目录执行 | 1. 在空目录执行 `python -m src project_diff projA`。<br>2. 查看 `projects/repositories.json`。 | `repositories` 为空，`discovery_type` 为空；命令不崩溃。 | P2 | 边界 |

## 4. Hook 注册与执行（src/hooks/*）

| 用例ID | 模块 | 用例名称 | 前置条件 | 步骤 | 预期结果 | 优先级 | 类型 |
|---|---|---|---|---|---|---|---|
| HOOK-001 | Hook注册 | 注册全局 Hook 并按优先级排序 | 可在测试脚本中导入 hooks 模块 | 1. 通过小脚本注册两个 Hook：优先级 HIGH 与 LOW。<br>2. 调用 `get_hooks` 获取列表。 | Hook 列表按优先级从高到低排序。 | P2 | 功能 |
| HOOK-002 | Hook注册 | 同名 Hook 覆盖 | 同上 | 1. 注册同名 Hook 两次。<br>2. 观察日志并查询 Hook 列表。 | 日志提示覆盖；最终只保留最新注册的 Hook。 | P2 | 兼容性 |
| HOOK-003 | Hook查询 | 平台 Hook 与全局 Hook 合并 | 同上 | 1. 注册全局 Hook 与平台 Hook（platform=platA）。<br>2. 调用 `get_hooks(HookType.BUILD, platform='platA')`。 | 返回列表包含全局与平台 Hook，按优先级排序。 | P1 | 功能 |
| HOOK-004 | Hook执行 | Hook 返回 False 中断执行 | 同上 | 1. 注册两个 Hook，第一个返回 False。<br>2. 调用 `execute_hooks`。 | 执行在第一个 Hook 处停止并返回 False。 | P1 | 异常 |
| HOOK-005 | Hook执行 | Hook 异常在 stop_on_error=False 时不中断 | 同上 | 1. 注册一个抛异常的 Hook 与一个正常 Hook。<br>2. 调用 `execute_hooks(stop_on_error=False)`。 | 异常被记录但继续执行后续 Hook；整体返回 True。 | P2 | 兼容性 |
| HOOK-006 | Hook执行 | execute_single_hook 找不到目标 | 同上 | 1. 调用 `execute_single_hook` 指定不存在的 hook_name。 | 返回 success=False 且包含错误信息。 | P2 | 异常 |
| HOOK-007 | Hook验证 | 无参数 Hook 判为无效 | 同上 | 1. 注册一个无参数函数。<br>2. 调用 `validate_hooks`。 | invalid_hooks 中包含该 Hook，valid=False。 | P2 | 功能 |
| HOOK-008 | Hook回退 | 平台 Hook 失败后回退到全局 Hook | 同上 | 1. 注册平台 Hook 返回 False。<br>2. 注册全局 Hook 返回 True。<br>3. 调用 `execute_hooks_with_fallback(..., platform='platA')`。 | 平台 Hook 失败后执行全局 Hook 并返回 True。 | P1 | 功能 |

## 5. 主板与项目管理（src/plugins/project_manager.py）

| 用例ID | 模块 | 用例名称 | 前置条件 | 步骤 | 预期结果 | 优先级 | 类型 |
|---|---|---|---|---|---|---|---|
| PM-001 | 主板管理 | board_new 创建成功（有模板） | `projects/template/template.ini` 与 `projects/template/po` 存在 | 1. 执行 `python -m src board_new boardTest`。<br>2. 检查 `projects/boardTest/boardTest.ini` 与 `projects/boardTest/po`。 | 主板目录创建成功，ini 内容来自模板首个 section 被替换为 boardTest；po 目录被复制。 | P0 | 功能 |
| PM-002 | 主板管理 | board_new 创建成功（无模板） | 临时将 `projects/template` 改名或移走 | 1. 执行 `python -m src board_new boardNoTpl`。<br>2. 检查 ini 与 po 目录结构。<br>3. 恢复模板目录。 | 使用默认 ini 内容创建；po 目录含 `po_template/patches` 与 `overrides`。 | P1 | 兼容性 |
| PM-003 | 主板管理 | board_new 拒绝非法名称（空/./..） | 无 | 1. 依次执行 `python -m src board_new ""`、`python -m src board_new .`、`python -m src board_new ..`。 | 均返回错误提示，未创建目录。 | P1 | 异常 |
| PM-004 | 主板管理 | board_new 拒绝包含路径分隔符或绝对路径 | 无 | 1. 执行 `python -m src board_new a/b`。<br>2. 执行 `python -m src board_new /abs/path`。 | 均返回错误提示，未创建目录。 | P1 | 异常 |
| PM-005 | 主板管理 | board_new 拒绝保留名称 | 无 | 1. 执行 `python -m src board_new common`。 | 返回保留名错误，未创建目录。 | P1 | 异常 |
| PM-006 | 主板管理 | board_new 已存在时失败 | 已存在 `projects/boardA` | 1. 执行 `python -m src board_new boardA`。 | 返回“已存在”错误，不覆盖原目录。 | P1 | 异常 |
| PM-007 | 主板管理 | board_del 删除成功并清理缓存 | 已存在 `projects/boardTest` | 1. 执行 `python -m src board_del boardTest`。<br>2. 检查 `projects/boardTest` 是否被删除。<br>3. 检查 `.cache/projects/boardTest` 等缓存是否被删除。 | 主板目录删除；缓存目录若存在被清理；projects.json 索引被更新。 | P0 | 功能 |
| PM-008 | 主板管理 | board_del 受保护主板不可删除 | 设置 env `protected_boards` 包含 boardA（需脚本调用） | 1. 通过脚本调用 `board_del` 并传入保护列表。 | 返回受保护错误，不删除。 | P1 | 异常 |
| PM-009 | 项目管理 | project_new 创建成功并追加 ini | 已完成数据集A | 1. 执行 `python -m src project_new projA-new`（确保 `projA` 存在且可作为父项目）。<br>2. 查看 `projects/boardA/boardA.ini` 末尾是否追加 section。 | 追加新 section；`PROJECT_NAME` 由平台+项目名+客户拼接；INI 保留原注释。 | P0 | 功能 |
| PM-010 | 项目管理 | project_new 无法确定主板 | 保证项目名无父且无匹配前缀 | 1. 执行 `python -m src project_new unknownProj`。 | 输出无法确定主板的提示并失败。 | P1 | 异常 |
| PM-011 | 项目管理 | project_new 拒绝与 board 同名 | 已存在 boardA | 1. 执行 `python -m src project_new boardA`。 | 返回错误提示，不写入 ini。 | P1 | 异常 |
| PM-012 | 项目管理 | project_new 重复项目拒绝 | 已存在 projA | 1. 执行 `python -m src project_new projA`。 | 返回项目已存在错误，不写入 ini。 | P1 | 异常 |
| PM-013 | 项目管理 | project_del 删除项目与子项目 | 已完成数据集A，存在 `projA-sub` | 1. 执行 `python -m src project_del projA`。<br>2. 检查 ini 中 `projA` 与 `projA-sub` section 是否被移除。 | 删除主项目及所有子项目 section。 | P0 | 功能 |
| PM-014 | 项目管理 | project_del 项目不存在提示 | 已完成数据集A | 1. 执行 `python -m src project_del not_exist_proj`。 | 输出不存在提示，但流程可继续完成；ini 未被破坏。 | P2 | 兼容性 |

## 6. 构建与 Diff（src/plugins/project_builder.py）

| 用例ID | 模块 | 用例名称 | 前置条件 | 步骤 | 预期结果 | 优先级 | 类型 |
|---|---|---|---|---|---|---|---|
| BUILD-001 | Diff | 单仓库 diff 结构生成 | 已完成数据集A，且仓库有未提交改动 | 1. 执行 `python -m src project_diff projA`。<br>2. 查找 `.cache/build/projA/<timestamp>/diff`。 | 生成 `after/before/patch/commit` 目录；单仓库不包含 repo 子目录。 | P1 | 功能 |
| BUILD-002 | Diff | 多仓库 diff 结构生成 | 已完成数据集B，且 repo1/repo2 有改动 | 1. 执行 `python -m src project_diff projA`。<br>2. 查看 `after/before/patch/commit` 内是否含 repo1/repo2 子目录。 | 多仓库情况下各 repo 文件按子目录归档。 | P1 | 功能 |
| BUILD-003 | Diff | 无改动时不生成 patch 文件 | 工作区干净 | 1. 确保 `git status` 无变更。<br>2. 执行 `python -m src project_diff projA`。<br>3. 检查 `patch` 目录。 | `changes_worktree.patch` 与 `changes_staged.patch` 不生成或为空。 | P2 | 边界 |
| BUILD-004 | Diff | keep-diff-dir 保留原目录 | 已完成数据集A | 1. 执行 `python -m src project_diff projA --keep-diff-dir`。<br>2. 检查 diff 目录是否仍存在。 | tar.gz 生成后 diff 目录仍保留。 | P2 | 功能 |
| BUILD-005 | 构建流程 | 平台验证 Hook 失败终止构建 | 注册平台 VALIDATION Hook 返回 False | 1. 通过脚本注册 Hook。<br>2. 执行 `python -m src project_build projA`。 | 构建在验证阶段终止并返回 False。 | P1 | 异常 |
| BUILD-006 | 构建流程 | pre/build/post Hook 失败中止 | 注册对应平台 Hook 返回 False | 1. 注册 PRE_BUILD 或 BUILD 或 POST_BUILD Hook 返回 False。<br>2. 执行 `python -m src project_build projA`。 | 构建在对应阶段终止；日志提示失败阶段。 | P1 | 异常 |
| BUILD-007 | 构建流程 | 无平台时跳过 Hook | 确保项目配置无 PROJECT_PLATFORM | 1. 选择无平台配置的项目执行 `python -m src project_build <proj>`。 | 不触发平台 Hook；执行 pre/do/post 函数。 | P2 | 功能 |

## 7. PO 解析与应用（src/plugins/patch_override.py）

| 用例ID | 模块 | 用例名称 | 前置条件 | 步骤 | 预期结果 | 优先级 | 类型 |
|---|---|---|---|---|---|---|---|
| PO-001 | PO配置 | parse_po_config 基本解析 | 无 | 1. 在 Python REPL 执行 `from src.plugins.patch_override import parse_po_config`。<br>2. 调用 `parse_po_config("po1 po2 -po3 -po4[file1 file2]")`。 | apply_pos 包含 `po1` `po2`；exclude_pos 包含 `po3`；exclude_files 中 `po4` 包含 file1/file2。 | P1 | 功能 |
| PO-002 | PO应用 | PROJECT_PO_CONFIG 为空时直接返回 | 修改项目配置使 PROJECT_PO_CONFIG 为空 | 1. 执行 `python -m src po_apply projA`。 | 提示无 PO 配置并返回 True；不创建 po_applied。 | P2 | 边界 |
| PO-003 | PO应用 | 找不到 board_name 失败 | 在 projects_info 中移除 board_name（需脚本调用） | 1. 通过脚本调用 `po_apply`。 | 返回 False，日志提示无法找到 board_name。 | P1 | 异常 |
| PO-004 | PO应用 | 已应用的 PO 被跳过 | 在 `projects/boardA/po/po_base/po_applied` 创建文件 | 1. 执行 `python -m src po_apply projA`。 | 日志提示该 PO 已应用并跳过；不重复执行补丁/覆盖。 | P2 | 兼容性 |
| PO-005 | PO应用 | patch 应用成功 | 已准备补丁文件与 Git 仓库 | 1. 执行 `python -m src po_apply projA`。<br>2. 检查补丁对应的代码文件已被修改。 | `git apply` 成功；日志显示 patch applied；po_applied 文件记录执行命令。 | P0 | 功能 |
| PO-006 | PO应用 | patch 失败时终止 | 准备与当前仓库不匹配的 patch | 1. 执行 `python -m src po_apply projA`。 | 日志报 patch apply 失败并返回 False；后续 override/custom 不执行。 | P0 | 异常 |
| PO-007 | PO应用 | override 复制成功 | 在 overrides 下准备文件 | 1. 执行 `python -m src po_apply projA`。<br>2. 验证目标文件被覆盖（内容一致）。 | 覆盖文件被拷贝到目标位置；日志显示 Copy override file。 | P1 | 功能 |
| PO-008 | PO应用 | .remove 文件触发删除 | 在 overrides 下创建 `path/to/file.remove` | 1. 确保目标文件存在。<br>2. 执行 `python -m src po_apply projA`。 | 目标文件被删除；日志显示 Remove file。 | P1 | 功能 |
| PO-009 | PO应用 | exclude_files 跳过指定文件 | 在 PROJECT_PO_CONFIG 中配置 `po_base[file.remove]` | 1. 执行 `python -m src po_apply projA`。 | 指定文件被跳过，未执行 copy/remove。 | P2 | 功能 |
| PO-010 | PO应用 | custom 目录按配置复制 | 已完成数据集A中的 custom 文件 | 1. 执行 `python -m src po_apply projA`。<br>2. 检查 `out/cfg/sample.ini` 与 `out/data/sample.dat`。 | custom 文件按规则拷贝到目标路径。 | P1 | 功能 |
| PO-011 | PO回滚 | patch 反向应用成功 | 已执行过 PO-005 | 1. 执行 `python -m src po_revert projA`。<br>2. 检查补丁带来的修改已撤销。 | `git apply --reverse` 成功；代码恢复。 | P1 | 功能 |
| PO-012 | PO回滚 | override 回滚（受 Git 跟踪） | override 目标文件为 Git 跟踪文件 | 1. 执行 `python -m src po_revert projA`。 | 目标文件通过 `git checkout --` 恢复。 | P1 | 功能 |
| PO-013 | PO回滚 | override 回滚（未跟踪） | 目标文件为未跟踪文件 | 1. 执行 `python -m src po_revert projA`。 | 目标文件被直接删除。 | P1 | 功能 |
| PO-014 | PO回滚 | custom 回滚提示人工处理 | 已配置 PROJECT_PO_FILE_COPY | 1. 执行 `python -m src po_revert projA`。<br>2. 查看日志。 | 日志提示 custom 文件需要人工清理；流程仍返回 True。 | P2 | 兼容性 |

## 8. PO 创建、更新、删除与列表（src/plugins/patch_override.py）

| 用例ID | 模块 | 用例名称 | 前置条件 | 步骤 | 预期结果 | 优先级 | 类型 |
|---|---|---|---|---|---|---|---|
| PO-015 | PO创建 | po_new 拒绝非法名称 | 已完成数据集A | 1. 执行 `python -m src po_new projA PO-INVALID`。 | 返回错误，提示仅允许 `po[a-z0-9_]*`。 | P1 | 异常 |
| PO-016 | PO创建 | po_new force 创建空结构 | 已完成数据集A | 1. 执行 `python -m src po_new projA po_force --force`。<br>2. 检查 `projects/boardA/po/po_force/patches` 与 `overrides` 目录。 | 目录结构创建成功，无交互提示。 | P1 | 功能 |
| PO-017 | PO创建 | po_new 交互式选择文件 | 工作区有修改/删除文件 | 1. 执行 `python -m src po_new projA po_interactive`。<br>2. 在交互中选择文件并选择创建 patch/override/remove。 | 选择的文件被正确处理；patch/override/remove 文件生成。 | P1 | 功能 |
| PO-018 | PO创建 | po_new 无仓库时提示 | `env['repositories']` 为空（在无 Git 的目录执行） | 1. 在无 Git 目录执行 `python -m src po_new projA po_empty`。 | 提示无仓库，交互结束；不崩溃。 | P2 | 边界 |
| PO-019 | PO更新 | po_update 要求 PO 已存在 | 已完成数据集A | 1. 先创建 `po_update_target`。<br>2. 执行 `python -m src po_update projA po_update_target --force`。 | 更新流程执行成功；复用 po_new 逻辑。 | P1 | 功能 |
| PO-020 | PO更新 | po_update PO 不存在时报错 | 已完成数据集A | 1. 执行 `python -m src po_update projA po_not_exists --force`。 | 报错提示 PO 目录不存在。 | P1 | 异常 |
| PO-021 | PO删除 | po_del 删除目录与配置 | 已存在 PO 且在 PROJECT_PO_CONFIG 中引用 | 1. 执行 `python -m src po_del projA po_base --force`。<br>2. 检查 po 目录被删除。<br>3. 检查 ini 中 `PROJECT_PO_CONFIG` 不再包含该 PO。 | PO 目录删除成功，配置中被移除。 | P0 | 功能 |
| PO-022 | PO删除 | po_del 交互取消 | 已存在 PO | 1. 执行 `python -m src po_del projA po_base`。<br>2. 输入 `no`。 | 删除取消，PO 目录与配置不变。 | P2 | 兼容性 |
| PO-023 | PO列表 | po_list short 仅列名称 | 已完成数据集A | 1. 执行 `python -m src po_list projA --short`。 | 仅输出 PO 名称列表。 | P1 | 功能 |
| PO-024 | PO列表 | po_list 详细输出 patch/override/custom | 已完成数据集A | 1. 执行 `python -m src po_list projA`。 | 输出包含 patch、override、custom 文件列表。 | P1 | 功能 |

## 9. 工具与日志（src/utils.py / src/log_manager.py / src/profiler.py）

| 用例ID | 模块 | 用例名称 | 前置条件 | 步骤 | 预期结果 | 优先级 | 类型 |
|---|---|---|---|---|---|---|---|
| UTIL-001 | 工具 | get_version 读取 pyproject | 已完成数据集A | 1. 执行 `python -c "from src.utils import get_version; print(get_version())"`。<br>2. 对比 `pyproject.toml` 中的版本。 | 输出版本与 pyproject 一致。 | P2 | 功能 |
| UTIL-002 | 工具 | get_version 缺失时回退 | 临时将 `pyproject.toml` 改名 | 1. 执行同上命令。<br>2. 恢复文件名。 | 输出 `0.0.0-dev`。 | P2 | 边界 |
| UTIL-003 | 工具 | get_filename 自动创建目录 | 删除 `.cache/logs` 目录 | 1. 执行 `python -c "from src.utils import get_filename; print(get_filename('T_', '.log', '.cache/logs'))"`。 | `.cache/logs` 被创建，返回路径包含时间戳。 | P3 | 功能 |
| UTIL-004 | 工具 | list_file_path 深度与过滤 | 创建测试目录结构 | 1. 创建 `tmp/a/b/file.txt`。<br>2. 执行 `python -c "from src.utils import list_file_path; print(list(list_file_path('tmp', max_depth=1)))"`。 | 输出不包含深度超过 1 的文件。 | P3 | 功能 |
| LOG-001 | 日志 | latest.log 软链接创建 | 已完成数据集A | 1. 运行任意命令（如 `python -m src --help`）。<br>2. 检查 `.cache/latest.log`。 | 软链接存在并指向最新日志文件。 | P2 | 功能 |
| PROF-001 | 性能分析 | ENABLE_CPROFILE 开关生效 | 设置 `builtins.ENABLE_CPROFILE=True` 的脚本 | 1. 写脚本调用被 `@func_cprofile` 装饰的方法。 | 日志输出 cProfile 统计信息；程序正常结束。 | P3 | 功能 |
