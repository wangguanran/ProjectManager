name: quick-task
description: "快速任务流程：简单任务的快速执行（无需多轮确认）"

args:
  task_description:
    description: "任务描述"
    required: true
  agent_id:
    description: "执行 Agent ID (pm/builder/tester)"
    default: "builder"
  project_path:
    description: "项目根目录"
    default: "/home/wangguanran/ProjectManager"

env:
  PYTHONPATH: "$args.project_path/src"
  PROJECT_ROOT: "$args.project_path"

steps:
  # 任务执行
  - id: execute
    command: |
      openclaw.invoke --tool sessions_spawn --action spawn \
        --args-json '{
          "task": "$args.task_description",
          "label": "quick-task",
          "agentId": "$args.agent_id",
          "runTimeoutSeconds": 300,
          "cleanup": "delete"
        }'

  # 结果确认
  - id: confirm
    command: |
      echo "任务完成: $args.task_description"
      echo "执行 Agent: $args.agent_id"
    stdin: $execute.stdout
    approval: required
    prompt: "任务已完成。是否确认结果？"

  # 通知
  - id: notify
    command: |
      openclaw.invoke --tool message --action send \
        --args-json '{
          "provider": "whatsapp",
          "to": "+8613800000000",
          "message": "✅ 快速任务完成\n任务: $args.task_description"
        }'
    condition: $confirm.approved
