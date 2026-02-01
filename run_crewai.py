#!/usr/bin/env python3
"""
CrewAI 工作流启动脚本
ProjectManager - 多Agent协作开发流程

使用方法:
    python run_crewai.py "你的需求描述"

示例:
    python run_crewai.py "添加主板删除功能"
    python run_crewai.py "支持多语言文档"
    python run_crewai.py "优化PO应用性能"
"""

import os
import sys
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from crewai_agents.crew import ProjectManagerCrew


def main():
    """主入口函数"""
    if len(sys.argv) < 2:
        print("❌ 错误: 请提供需求描述")
        print("\n使用方法:")
        print(f"    python {sys.argv[0]} \"你的需求描述\"")
        print("\n示例:")
        print(f"    python {sys.argv[0]} \"添加主板删除功能\"")
        sys.exit(1)
    
    # 获取需求
    requirements = sys.argv[1]
    print(f"\n🚀 启动 CrewAI 工作流")
    print(f"📋 需求: {requirements}")
    print(f"⏰ 时间: {datetime.now().isoformat()}")
    print("-" * 60)
    
    # 创建工作流
    crew = ProjectManagerCrew(requirements=requirements)
    
    # 启动工作流
    result = crew.crew().kickoff()
    
    print("\n" + "=" * 60)
    print("✅ 工作流执行完成")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    main()
