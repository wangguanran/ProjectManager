#!/usr/bin/env python3
"""
CrewAI 工作流启动脚本
ProjectManager - 多Agent协作开发流程

使用: python run_workflow.py "你的需求描述"
示例: python run_workflow.py "添加主板删除功能"
"""

import sys
import os

# 确保路径正确
sys.path.insert(0, os.path.dirname(__file__))

from crewai_agents.workflow import WorkflowEngine, main


if __name__ == "__main__":
    # 直接调用 main 函数（使用 sys.argv）
    main()
