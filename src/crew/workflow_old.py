"""CrewAI-based workflow orchestrator."""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from src.log_manager import log

from .agents import TaskStore, TaskTrackerAgent, TestCaseStore
from .llm_config import LLMConfig, load_llm_config
from .models import CrewRequest, RequestType, Task, TaskStatus, TestCase, WorkflowResult


class TestCaseOutput(BaseModel):
    case_id: str
    title: str
    steps: List[str]
    expected: List[str]
    priority: str = "P1"
    case_type: str = "functional"
    scope: str = "blackbox"


class RequirementOutput(BaseModel):
    request_type: str
    title: str
    details: str
    confirmed: bool = False
    conflict: bool = False
    notes: str = ""
    bug_gap: Optional[str] = None
    optimization_scope: Optional[str] = None
    blackbox_cases: List[TestCaseOutput] = Field(default_factory=list)


class TaskOutput(BaseModel):
    task_id: str
    title: str
    description: str
    assignee: str = "C"


class TaskBreakdownOutput(BaseModel):
    tasks: List[TaskOutput]


class ReviewOutput(BaseModel):
    approved: bool
    notes: str = ""


class TestPlanOutput(BaseModel):
    blackbox_cases: List[TestCaseOutput] = Field(default_factory=list)
    whitebox_cases: List[TestCaseOutput] = Field(default_factory=list)
    verification_notes: str = ""


class TestExecutionOutput(BaseModel):
    passed: bool
    missing_coverage: List[str] = Field(default_factory=list)
    notes: str = ""


class TaskClosureOutput(BaseModel):
    commit_message: str
    status_summary: str = ""


class CrewWorkflow:
    """End-to-end workflow following A -> B -> C -> D -> E -> F -> A."""

    def __init__(
        self,
        tasks_path: str,
        test_cases_path: str,
        prompt_fn: Optional[Callable[[str], str]] = None,
        test_runner: Optional[Callable[[], bool]] = None,
        llm_config: Optional[LLMConfig] = None,
    ) -> None:
        self.task_store = TaskStore(tasks_path)
        self.case_store = TestCaseStore(test_cases_path)
        self.task_tracker = TaskTrackerAgent(task_updater=self.task_store.update)
        self.prompt_fn = prompt_fn or (lambda msg: input(msg))
        self.test_runner = test_runner
        self.llm_config = llm_config or load_llm_config()

    def run(self, request: CrewRequest, auto_confirm: bool = False) -> WorkflowResult:
        log.info("CrewAI workflow started: %s", request.title)

        if auto_confirm:
            request.confirmed = True

        llm = self._build_llm(self.llm_config)
        if llm is None:
            return WorkflowResult(False, "CrewAI is not installed. Please install the 'crewai' package.")

        analysis_agent, architect_agent, code_agent, review_agent, test_agent, exec_agent, tracker_agent = (
            self._build_agents(llm)
        )

        analysis_task = self._build_analysis_task(analysis_agent, human_input=not auto_confirm)
        architect_task = self._build_architect_task(architect_agent, analysis_task)
        code_task = self._build_code_task(code_agent, architect_task)
        review_task = self._build_review_task(review_agent, code_task)
        test_task = self._build_test_task(test_agent, review_task)
        exec_task = self._build_exec_task(exec_agent, test_task)
        tracker_task = self._build_tracker_task(tracker_agent, exec_task)

        crew = self._build_crew(
            [analysis_agent, architect_agent, code_agent, review_agent, test_agent, exec_agent, tracker_agent],
            [
                analysis_task,
                architect_task,
                code_task,
                review_task,
                test_task,
                exec_task,
                tracker_task,
            ],
        )

        inputs = {
            "request_type": request.request_type.value,
            "title": request.title,
            "details": request.details,
        }
        try:
            crew.kickoff(inputs=inputs)
        except Exception as exc:  # noqa: BLE001
            log.error("CrewAI kickoff failed: %s", exc)
            return WorkflowResult(False, f"CrewAI kickoff failed: {exc}")

        requirement = self._read_output(analysis_task, RequirementOutput)
        if requirement is None:
            return WorkflowResult(False, "Requirement analysis output missing")
        if auto_confirm:
            requirement.confirmed = True
        if not requirement.confirmed:
            return WorkflowResult(False, "Request not confirmed")

        req_type = requirement.request_type.strip().lower()
        existing_cases = self.case_store.load_existing(self.case_store.path)
        if self._detect_conflicts(requirement.title, existing_cases) or requirement.conflict:
            answer = self.prompt_fn(
                "Conflicting test cases detected. Type 'yes' to proceed, anything else to stop: "
            ).strip()
            if answer.lower() != "yes":
                return WorkflowResult(False, "Conflict detected with existing test cases")

        test_cases = self._convert_cases(requirement.blackbox_cases, scope="blackbox")
        if req_type == RequestType.OPTIMIZATION.value:
            log.info("Optimization request: skip blackbox test case updates")
            test_cases = []
        elif test_cases:
            self.case_store.write(test_cases)

        if req_type == RequestType.BUG.value and requirement.bug_gap:
            log.info("Bug analysis: %s", requirement.bug_gap)
        if req_type == RequestType.OPTIMIZATION.value and requirement.optimization_scope:
            log.info("Optimization scope: %s", requirement.optimization_scope)

        task_breakdown = self._read_output(architect_task, TaskBreakdownOutput)
        if task_breakdown is None:
            return WorkflowResult(False, "Task breakdown output missing")
        tasks = self._convert_tasks(task_breakdown.tasks)
        self.task_store.write(tasks)

        review = self._read_output(review_task, ReviewOutput)
        if review is None or not review.approved:
            notes = review.notes if review else "Review output missing"
            return WorkflowResult(False, f"Review failed: {notes}", tasks=tasks)

        test_plan = self._read_output(test_task, TestPlanOutput)
        if test_plan:
            new_cases: List[TestCase] = []
            if req_type != RequestType.OPTIMIZATION.value:
                new_cases.extend(self._convert_cases(test_plan.blackbox_cases, scope="blackbox"))
            new_cases.extend(self._convert_cases(test_plan.whitebox_cases, scope="whitebox"))
            if new_cases:
                self.case_store.write(new_cases)

        exec_result = self._read_output(exec_task, TestExecutionOutput)
        if exec_result is None:
            return WorkflowResult(False, "Test execution output missing", tasks=tasks)

        runner_ok = True
        if self.test_runner:
            runner_ok = self.test_runner()
        if not exec_result.passed or not runner_ok:
            return WorkflowResult(
                False,
                "Tests failed",
                tasks=tasks,
                tests_added=test_cases,
            )

        self.task_tracker.close_tasks(tasks)

        tracker_output = self._read_output(tracker_task, TaskClosureOutput)
        commit_message = (
            tracker_output.commit_message if tracker_output and tracker_output.commit_message else None
        )
        if not commit_message:
            commit_message = self.task_tracker.generate_commit_message(tasks)
        return WorkflowResult(True, f"Workflow complete. Commit message: {commit_message}", tasks=tasks)

    @staticmethod
    def _normalize_model(config: LLMConfig) -> str:
        if "/" in config.model:
            return config.model
        if config.provider:
            return f"{config.provider}/{config.model}"
        return config.model

    def _build_llm(self, config: LLMConfig):
        try:
            from crewai import LLM
        except ImportError:
            return None

        model = self._normalize_model(config)
        params: Dict[str, Any] = {"model": model}
        if config.provider:
            params["provider"] = config.provider
            params["custom_llm_provider"] = config.provider
            if "/" in model and not model.startswith("minimax/"):
                params["model"] = model.split("/", 1)[1]
        credential = config.credential()
        if credential:
            params["api_key"] = credential
            if config.auth_mode == "oauth":
                params["access_token"] = credential
        if config.base_url:
            params["base_url"] = config.base_url
            params["api_base"] = config.base_url
        if config.temperature is not None:
            params["temperature"] = config.temperature
        if config.max_tokens is not None:
            params["max_tokens"] = config.max_tokens
        return LLM(**params)

    def _build_agents(self, llm):
        from crewai import Agent

        analysis_agent = Agent(
            role="需求分析Agent",
            goal="与用户沟通确认需求并产出黑盒测试用例",
            backstory="负责澄清需求，识别冲突，并明确需求类型与约束。",
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )
        architect_agent = Agent(
            role="代码架构师Agent",
            goal="拆分任务并分配给工程师",
            backstory="将需求转化为可执行任务并记录。",
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )
        code_agent = Agent(
            role="代码编写工程师Agent",
            goal="根据任务实现代码并说明变更",
            backstory="专注于实现需求，不偏离任务范围。",
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )
        review_agent = Agent(
            role="Review工程师Agent",
            goal="Review实现并指出问题",
            backstory="关注风险、缺陷与遗漏并给出结论。",
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )
        test_agent = Agent(
            role="测试用例编写工程师Agent",
            goal="编写黑盒与白盒测试用例并验证单用例",
            backstory="确保测试覆盖需求与代码分支。",
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )
        exec_agent = Agent(
            role="测试用例执行Agent",
            goal="执行测试用例并评估完备性",
            backstory="运行测试并判断是否需要补充。",
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )
        tracker_agent = Agent(
            role="任务跟踪Agent",
            goal="更新任务状态并生成提交信息",
            backstory="收尾任务，生成提交信息与下一步建议。",
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )
        return (
            analysis_agent,
            architect_agent,
            code_agent,
            review_agent,
            test_agent,
            exec_agent,
            tracker_agent,
        )

    @staticmethod
    def _build_analysis_task(agent, human_input: bool = True):
        from crewai import Task

        return Task(
            description=(
                "你是需求分析Agent。结合用户需求{title}({request_type})进行澄清，必要时通过人类输入提问。"
                "request_type必须为new_requirement/bug/optimization之一。"
                "确认需求后输出JSON：request_type/title/details/confirmed/conflict/notes/bug_gap/"
                "optimization_scope/blackbox_cases。"
                "若是bug，说明黑盒还是白盒用例缺失；若是优化，说明仅允许内部逻辑与白盒用例变更。"
                "blackbox_cases需包含明确步骤与预期结果。"
            ),
            expected_output="结构化JSON，包含需求确认与黑盒用例列表",
            agent=agent,
            human_input=human_input,
            output_json=RequirementOutput,
        )

    @staticmethod
    def _build_architect_task(agent, analysis_task):
        from crewai import Task

        return Task(
            description=(
                "基于需求分析输出拆分任务，生成可执行任务列表并标注分配给C。"
                "输出JSON：tasks[{task_id,title,description,assignee}]。"
            ),
            expected_output="结构化JSON任务拆分",
            agent=agent,
            context=[analysis_task],
            output_json=TaskBreakdownOutput,
        )

    @staticmethod
    def _build_code_task(agent, architect_task):
        from crewai import Task

        return Task(
            description=(
                "根据任务拆分结果实现代码变更，输出实现说明、涉及文件与关键逻辑。"
                "不偏离任务范围。"
            ),
            expected_output="实现说明与变更摘要",
            agent=agent,
            context=[architect_task],
        )

    @staticmethod
    def _build_review_task(agent, code_task):
        from crewai import Task

        return Task(
            description=(
                "Review代码实现，判断是否通过并指出问题。输出JSON：approved/notes。"
            ),
            expected_output="结构化Review结论",
            agent=agent,
            context=[code_task],
            output_json=ReviewOutput,
        )

    @staticmethod
    def _build_test_task(agent, review_task):
        from crewai import Task

        return Task(
            description=(
                "基于Review通过的实现编写测试用例：黑盒与白盒。黑盒需与docs记录一一对应，"
                "白盒覆盖代码分支。若为优化需求，黑盒用例不变，仅输出白盒用例。"
                "输出JSON：blackbox_cases/whitebox_cases/verification_notes。"
            ),
            expected_output="结构化测试用例列表",
            agent=agent,
            context=[review_task],
            output_json=TestPlanOutput,
        )

    @staticmethod
    def _build_exec_task(agent, test_task):
        from crewai import Task

        return Task(
            description=(
                "执行全部测试用例并评估完备性。输出JSON：passed/missing_coverage/notes。"
            ),
            expected_output="结构化测试执行结果",
            agent=agent,
            context=[test_task],
            output_json=TestExecutionOutput,
        )

    @staticmethod
    def _build_tracker_task(agent, exec_task):
        from crewai import Task

        return Task(
            description=(
                "更新任务状态，生成提交信息与下一步建议。输出JSON：commit_message/status_summary。"
            ),
            expected_output="结构化收尾信息",
            agent=agent,
            context=[exec_task],
            output_json=TaskClosureOutput,
        )

    @staticmethod
    def _build_crew(agents, tasks):
        from crewai import Crew, Process

        return Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=True,
        )

    @staticmethod
    def _read_output(task, model_cls):
        if not task.output:
            return None
        if hasattr(task.output, "pydantic") and task.output.pydantic:
            return task.output.pydantic
        if hasattr(task.output, "json_dict") and task.output.json_dict:
            return model_cls(**task.output.json_dict)
        raw = getattr(task.output, "raw", None) or str(task.output)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return model_cls(**data)

    @staticmethod
    def _detect_conflicts(title: str, existing_cases: List[TestCase]) -> bool:
        for case in existing_cases:
            if title.lower() in case.title.lower():
                return True
        return False

    @staticmethod
    def _convert_cases(cases: List[TestCaseOutput], scope: str) -> List[TestCase]:
        converted: List[TestCase] = []
        for idx, case in enumerate(cases, start=1):
            case_id = case.case_id or f"AUTO-{idx:03d}"
            converted.append(
                TestCase(
                    case_id=case_id,
                    title=case.title,
                    steps=case.steps,
                    expected=case.expected,
                    priority=case.priority,
                    case_type=case.case_type,
                    scope=case.scope or scope,
                )
            )
        return converted

    @staticmethod
    def _convert_tasks(tasks: List[TaskOutput]) -> List[Task]:
        converted: List[Task] = []
        for task in tasks:
            converted.append(
                Task(
                    task_id=task.task_id,
                    title=task.title,
                    description=task.description,
                    assignee=task.assignee,
                    status=TaskStatus.TODO,
                )
            )
        return converted


def default_tasks_path() -> str:
    return os.path.join(os.getcwd(), "docs", "tasks.md")


def default_test_cases_path() -> str:
    return os.path.join(os.getcwd(), "docs", "test_cases_crew.md")
