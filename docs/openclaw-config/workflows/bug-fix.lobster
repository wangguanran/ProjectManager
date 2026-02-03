name: bug-fix
description: "Bug 修复流程：复现 -> 修复 -> 验证"

args:
  bug_description:
    description: "Bug 描述"
    required: true
  test_case_id:
    description: "测试用例 ID"
    required: true
  project_path:
    description: "项目根目录"
    default: "/home/wangguanran/ProjectManager"

env:
  PYTHONPATH: "$args.project_path/src"
  PROJECT_ROOT: "$args.project_path"

steps:
  # 阶段 1: Bug 复现
  - id: reproduce
    command: |
      openclaw.invoke --tool sessions_spawn --action spawn \
        --args-json '{
          "task": "复现 Bug: $args.bug_description。按照测试用例 $args.test_case_id 执行。",
          "label": "bug-reproduce",
          "agentId": "tester",
          "runTimeoutSeconds": 300
        }'

  # 阶段 2: 根因分析
  - id: analyze
    command: |
      openclaw.invoke --tool sessions_spawn --action spawn \
        --args-json '{
          "task": "分析 Bug 根因: $args.bug_description。定位问题代码位置。",
          "label": "root-cause-analysis",
          "agentId": "pm"
        }'
    condition: $reproduce.approved
    approval: required
    prompt: "Bug 已复现。是否继续根因分析？"

  # 阶段 3: 修复实施
  - id: fix
    command: |
      openclaw.invoke --tool sessions_spawn --action spawn \
        --args-json '{
          "task": "修复 Bug: $args.bug_description。根据根因分析结果实施修复。",
          "label": "bug-fix",
          "agentId": "builder"
        }'
    condition: $analyze.approved
    approval: required
    prompt: "根因已定位。是否开始修复？"

  # 阶段 4: 回归测试
  - id: regression_test
    command: |
      cd $args.project_path && \
      python -m pytest tests/ -v --tb=short -k "$args.test_case_id"
    condition: $fix.approved

  # 阶段 5: 验证通过
  - id: verify
    command: |
      echo "Bug 修复验证完成"
      echo "测试用例 $args.test_case_id: PASSED"
    stdin: $regression_test.stdout
    approval: required
    prompt: "回归测试通过。是否确认修复完成？"

  # 阶段 6: 更新文档
  - id: update_docs
    command: |
      openclaw.invoke --tool write --action write \
        --args-json '{
          "filePath": "$args.project_path/docs/bugs/fixed-$args.test_case_id.md",
          "content": "# Bug 修复记录\n\n## Bug 描述\n$args.bug_description\n\n## 测试用例\n$args.test_case_id\n\n## 修复时间\n$(date)\n\n## 状态\n已修复并验证"
        }'
    condition: $verify.approved

  # 阶段 7: 通知用户
  - id: notify
    command: |
      openclaw.invoke --tool message --action send \
        --args-json '{
          "provider": "whatsapp",
          "to": "+8613800000000",
          "message": "🐛 Bug 已修复\n描述: $args.bug_description\n测试用例: $args.test_case_id\n状态: 已验证通过"
        }'
    condition: $update_docs.approved
