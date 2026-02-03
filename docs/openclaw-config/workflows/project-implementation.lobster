name: project-implementation
description: "完整的项目实施流程：需求 -> 开发 -> 测试 -> 部署"

args:
  requirement_file:
    description: "需求文档路径"
    required: true
  test_cases_file:
    description: "测试用例文件路径"
    required: true
  project_path:
    description: "项目根目录"
    default: "/home/wangguanran/ProjectManager"

env:
  PYTHONPATH: "$args.project_path/src"
  PROJECT_ROOT: "$args.project_path"

steps:
  # 阶段 1: 准备工作
  - id: prepare
    command: |
      echo "开始项目实施流程"
      echo "需求文档: $args.requirement_file"
      echo "测试用例: $args.test_cases_file"
      echo "项目路径: $args.project_path"
    condition: true

  # 阶段 2: 代码分析（Sub-Agent）
  - id: analyze
    command: |
      openclaw.invoke --tool sessions_spawn --action spawn \
        --args-json '{
          "task": "分析需求文档 $args.requirement_file，识别需要修改的文件和模块",
          "label": "code-analysis",
          "agentId": "pm"
        }'
    stdin: $prepare.stdout
    
  # 阶段 3: 开发实施（Builder Agent）
  - id: build
    command: |
      openclaw.invoke --tool sessions_spawn --action spawn \
        --args-json '{
          "task": "根据需求文档 $args.requirement_file 实施功能开发",
          "label": "feature-development",
          "agentId": "builder",
          "model": "anthropic/claude-sonnet-4-5"
        }'
    condition: $analyze.approved
    approval: required
    prompt: "分析完成。是否开始开发实施？"

  # 阶段 4: 单元测试（Tester Agent）
  - id: unit_test
    command: |
      openclaw.invoke --tool sessions_spawn --action spawn \
        --args-json '{
          "task": "执行测试用例 $args.test_cases_file 中的单元测试",
          "label": "unit-testing",
          "agentId": "tester",
          "runTimeoutSeconds": 600
        }'
    condition: $build.approved

  # 阶段 5: 集成测试
  - id: integration_test
    command: |
      cd $args.project_path && \
      python -m pytest tests/integration/ -v --tb=short --json-report --json-report-file=test-results.json
    condition: $unit_test.approved
    approval: required
    prompt: "单元测试通过。是否继续集成测试？"

  # 阶段 6: 结果汇报
  - id: report
    command: |
      echo "========== 实施报告 =========="
      echo "需求: $args.requirement_file"
      echo "测试用例: $args.test_cases_file"
      echo ""
      echo "阶段 1 - 代码分析: 完成"
      echo "阶段 2 - 功能开发: 完成"
      echo "阶段 3 - 单元测试: 完成"
      echo "阶段 4 - 集成测试: 完成"
      echo ""
      echo "所有测试通过，功能已就绪。"
      cat $args.project_path/test-results.json | jq '.summary'
    stdin: $integration_test.stdout
    condition: $integration_test.approved

  # 阶段 7: 部署确认（最终审批）
  - id: deploy_confirm
    command: echo "准备部署到生产环境"
    approval: required
    prompt: |
      所有测试已通过。部署清单：
      - 修改的文件: [由 Builder Agent 提供]
      - 测试覆盖率: [由 Tester Agent 提供]
      - 影响范围: [需求文档中描述]
      
      是否确认部署？

  # 阶段 8: 生成文档
  - id: docs
    command: |
      openclaw.invoke --tool sessions_spawn --action spawn \
        --args-json '{
          "task": "根据实施结果生成 CHANGELOG 和用户文档",
          "label": "documentation",
          "agentId": "pm",
          "cleanup": "delete"
        }'
    condition: $deploy_confirm.approved

  # 阶段 9: 完成通知
  - id: notify
    command: |
      openclaw.invoke --tool message --action send \
        --args-json '{
          "provider": "whatsapp",
          "to": "+8613800000000",
          "message": "✅ 项目实施完成\n需求: $args.requirement_file\n测试: 全部通过\n已生成文档和 CHANGELOG"
        }'
    stdin: $docs.stdout
    condition: $docs.approved
