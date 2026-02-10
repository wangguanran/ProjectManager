"""
CrewAI workflow definition for ProjectManager.

This module is optional. If CrewAI is not installed, importing this file will
still succeed, but instantiating `ProjectManagerCrew` will raise an error with
installation instructions.
"""

from __future__ import annotations

import os
from typing import Optional

_CREWAI_IMPORT_ERROR: Optional[Exception] = None

try:
    from crewai import Agent, Crew, Process, Task  # pylint: disable=import-error
    from crewai.project import (  # pylint: disable=import-error
        CrewBase,
        agent,
        crew,
        task,
    )
except ImportError as exc:  # pragma: no cover
    _CREWAI_IMPORT_ERROR = exc

    Agent = object  # type: ignore
    Crew = object  # type: ignore
    Process = object  # type: ignore
    Task = object  # type: ignore

    def CrewBase(cls):  # type: ignore
        """No-op decorator stub when CrewAI is unavailable."""
        return cls

    def agent(func):  # type: ignore
        """No-op decorator stub when CrewAI is unavailable."""
        return func

    def crew(func):  # type: ignore
        """No-op decorator stub when CrewAI is unavailable."""
        return func

    def task(func):  # type: ignore
        """No-op decorator stub when CrewAI is unavailable."""
        return func


@CrewBase
class ProjectManagerCrew:
    """ProjectManager CrewAI 工作流"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self, requirements: Optional[str] = None):
        """初始化工作流.

        Args:
            requirements: 用户需求描述
        """
        if _CREWAI_IMPORT_ERROR is not None:
            raise RuntimeError(
                'CrewAI is not installed. Install optional dependencies with: pip install -e ".[crewai]"'
            ) from _CREWAI_IMPORT_ERROR
        self.requirements = requirements
        self.tasks_file = os.path.join(os.path.dirname(__file__), "..", "docs", "tasks.md")
        self.test_cases_file = os.path.join(os.path.dirname(__file__), "..", "docs", "test_cases_zh.md")

        # 确保 docs 目录存在
        os.makedirs(os.path.dirname(self.tasks_file), exist_ok=True)

    @agent
    def requirement_analyst_agent(self) -> Agent:
        """需求分析 Agent - 与用户对话明确需求，生成测试用例"""
        return Agent(
            name="需求分析 Agent",
            role="需求分析师",
            goal="深入理解用户需求，生成清晰、可测试的需求规格和测试用例",
            backstory="""你是一位资深的需求分析师，拥有10年以上软件工程经验。
            你擅长与用户沟通，挖掘真实需求，并将需求转化为可测试的规格说明。
            你精通各种测试方法论，包括黑盒测试、白盒测试、边界值分析等。
            你总是确保测试用例覆盖正常流程、边界条件和异常场景。""",
            verbose=True,
            allow_delegation=True,
            tools=[],  # 可以添加文件读写工具
        )

    @agent
    def architect_agent(self) -> Agent:
        """架构师 Agent - 分解任务，设计方案"""
        return Agent(
            name="架构师 Agent",
            role="系统架构师",
            goal="分析需求，分解任务，设计实现方案，协调各Agent工作",
            backstory="""你是一位经验丰富的系统架构师，精通软件设计模式和架构模式。
            你擅长将复杂需求分解为可执行的任务，并设计优雅的解决方案。
            你注重代码质量、可维护性和可扩展性。""",
            verbose=True,
            allow_delegation=True,
            tools=[],
        )

    @agent
    def coder_agent(self) -> Agent:
        """编码 Agent - 根据任务编写代码"""
        return Agent(
            name="编码 Agent",
            role="后端开发工程师",
            goal="根据任务要求，高质量地完成代码编写",
            backstory="""你是一位技术精湛的后端开发工程师，精通 Python。
            你遵循最佳实践，编写清晰、可维护的代码。
            你注重代码质量，包括适当的注释、类型提示和错误处理。""",
            verbose=True,
            allow_delegation=False,
            tools=[],  # 可以添加文件操作工具
        )

    @agent
    def review_agent(self) -> Agent:
        """Review Agent - 审核代码质量"""
        return Agent(
            name="Review Agent",
            role="代码审核工程师",
            goal="严格审核代码，确保代码质量、合规性和最佳实践",
            backstory="""你是一位严格的代码审核工程师，对代码质量有极高的标准。
            你熟悉各种代码规范和最佳实践，能够发现潜在的问题和改进点。
            你不会妥协代码质量，确保每一行代码都符合标准。""",
            verbose=True,
            allow_delegation=False,
            tools=[],
        )

    @agent
    def test_agent(self) -> Agent:
        """测试 Agent - 编写测试用例"""
        return Agent(
            name="测试 Agent",
            role="测试工程师",
            goal="编写全面、可靠的测试用例，确保功能正确性",
            backstory="""你是一位专业的测试工程师，精通测试用例设计。
            你熟悉 pytest 框架，能够编写各种类型的测试。
            你注重测试覆盖率，确保关键路径都经过测试。""",
            verbose=True,
            allow_delegation=False,
            tools=[],
        )

    @agent
    def executor_agent(self) -> Agent:
        """执行 Agent - 运行测试，确认结果"""
        return Agent(
            name="执行 Agent",
            role="CI/CD 工程师",
            goal="运行测试，分析结果，确保交付质量",
            backstory="""你是一位经验丰富的 CI/CD 工程师，负责自动化测试和部署。
            你熟悉各种测试工具和 CI/CD 流程，能够快速定位和解决问题。
            你注重效率，确保测试流程顺畅运行。""",
            verbose=True,
            allow_delegation=False,
            tools=[],  # 可以添加命令执行工具
        )

    # ========== TASKS ==========

    @task
    def analyze_requirements_task(self) -> Task:
        """需求分析任务"""
        return Task(
            description=f"""
            用户需求: {self.requirements}
            
            你的任务:
            1. 与用户对话，明确和细化需求
            2. 分析需求的完整性、一致性和可测试性
            3. 生成详细的测试用例，包括:
               - 测试场景描述
               - 前置条件
               - 测试步骤
               - 预期结果
               - 优先级
            4. 检查是否与现有需求冲突
            5. 更新 docs/test_cases_zh.md 文件
            
            注意:
            - 如果发现需求冲突，必须提醒用户并等待确认
            - 测试用例要覆盖正常流程、边界条件和异常场景
            - 保持测试用例的独立性和可重复性
            """,
            agent=self.requirement_analyst_agent(),
            expected_output="清晰的需求规格文档和完整的测试用例列表",
        )

    @task
    def design_and_decompose_task(self) -> Task:
        """架构设计和任务分解任务"""
        return Task(
            description="""
            你的任务:
            1. 接收并理解需求分析结果
            2. 设计实现方案，考虑:
               - 代码结构
               - 模块划分
               - 接口设计
               - 依赖关系
            3. 将需求分解为具体的开发任务
            4. 创建/更新 docs/tasks.md，记录:
               - 任务列表
               - 任务描述
               - 优先级
               - 依赖关系
               - 负责人
            5. 将任务分配给编码 Agent
            
            任务格式:
            ## 任务列表
            
            ### 任务 ID: TASK-001
            - **标题**: 任务标题
            - **描述**: 详细描述
            - **状态**: pending | in_progress | review | testing | done
            - **优先级**: high | medium | low
            - **负责人**: Agent 类型
            - **依赖**: 其他任务 ID
            - **创建时间**: ISO 格式时间
            """,
            agent=self.architect_agent(),
            expected_output="任务分解文档 (tasks.md)",
        )

    @task
    def coding_task(self) -> Task:
        """编码任务"""
        return Task(
            description="""
            你的任务:
            1. 从架构师接收具体任务
            2. 严格按照任务要求编写代码
            3. 确保代码质量:
               - 遵循 PEP 8 规范
               - 添加适当的注释
               - 使用类型提示
               - 错误处理完善
            4. 只能修改与任务相关的代码
            5. 完成後提交给 Review Agent
            
            重要:
            - 不要添加任务未要求的功能
            - 不要修改无关代码
            - 保持代码简洁
            """,
            agent=self.coder_agent(),
            expected_output="符合规范的代码实现",
        )

    @task
    def code_review_task(self) -> Task:
        """代码审核任务"""
        return Task(
            description="""
            你的任务:
            1. 接收编码 Agent 提交的代码
            2. 全面审核代码，包括:
               - 代码规范 (pylint, black)
               - 逻辑正确性
               - 安全性
               - 性能
               - 可维护性
            3. 检查是否满足任务要求
            4. 给出审核结果:
               - 通过: 交给测试 Agent
               - 不通过: 退回给编码 Agent 继续修改
            
            审核标准:
            - pylint 分数 >= 10/10
            - 所有测试通过
            - 代码覆盖率不降低
            """,
            agent=self.review_agent(),
            expected_output="审核通过或需要修改的反馈",
        )

    @task
    def write_test_cases_task(self) -> Task:
        """编写测试用例任务"""
        return Task(
            description="""
            你的任务:
            1. 接收需求和实现细节
            2. 根据功能编写测试用例
            3. 使用 pytest 框架
            4. 测试类型包括:
               - 单元测试
               - 集成测试
               - 边界测试
               - 异常测试
            5. 确保测试覆盖率
            6. 将测试用例交给执行 Agent
            
            注意事项:
            - 测试文件放在 tests/ 目录
            - 测试方法以 test_ 开头
            - 使用 pytest fixtures
            """,
            agent=self.test_agent(),
            expected_output="完整的测试用例文件",
        )

    @task
    def execute_and_verify_task(self) -> Task:
        """执行测试和验证任务"""
        return Task(
            description="""
            你的任务:
            1. 接收测试 Agent 编写的测试用例
            2. 运行测试套件
            3. 分析测试结果:
               - 通过的测试
               - 失败的测试
               - 覆盖率报告
            4. 判断测试用例是否完备:
               - 是否覆盖所有场景
               - 是否覆盖边界条件
               - 是否覆盖异常情况
            5. 如果不完备: 退回给测试 Agent 继续修改
            6. 如果通过:
               - 反馈给架构师
               - 更新 tasks.md 中的任务状态
               - 生成 commit message
               - 推送到服务器
            
            Commit Message 格式:
            <type>(<scope>): <subject>
            
            Types:
            - feat: 新功能
            - fix: 修复 bug
            - docs: 文档更新
            - style: 代码格式
            - refactor: 重构
            - test: 测试相关
            - chore: 其他
            
            Example:
            feat(board): 添加主板创建功能
            
            close #123
            """,
            agent=self.executor_agent(),
            expected_output="测试结果报告和代码提交",
        )

    @crew
    def crew(self) -> Crew:
        """创建 CrewAI 工作流"""
        return Crew(
            agents=[
                self.requirement_analyst_agent(),
                self.architect_agent(),
                self.coder_agent(),
                self.review_agent(),
                self.test_agent(),
                self.executor_agent(),
            ],
            tasks=[
                self.analyze_requirements_task(),
                self.design_and_decompose_task(),
                self.coding_task(),
                self.code_review_task(),
                self.write_test_cases_task(),
                self.execute_and_verify_task(),
            ],
            process=Process.sequential,  # 顺序执行
            verbose=True,
        )
