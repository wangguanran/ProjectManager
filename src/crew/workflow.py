"""Enhanced CrewAI-based workflow orchestrator with retry, tools, and memory."""

from __future__ import annotations

import json
import os
import time
import traceback
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from src.log_manager import log

from .agents import TaskStore, TaskTrackerAgent, TestCaseStore
from .exceptions import (
    AgentTimeoutError,
    ConfigurationError,
    LLMProviderError,
    MaxRetriesExceededError,
    ReviewFailedError,
    TestExecutionError,
)
from .llm_config import LLMConfig, LLMProviderConfig, load_llm_config, validate_config
from .models import CrewRequest, RequestType, Task, TaskStatus, TestCase, WorkflowResult
from .tools import get_all_tools, get_code_tools, get_safe_tools


class TestCaseOutput(BaseModel):
    """Output model for test cases."""

    case_id: str
    title: str
    steps: List[str]
    expected: List[str]
    priority: str = "P1"
    case_type: str = "functional"
    scope: str = "blackbox"


class RequirementOutput(BaseModel):
    """Output model for requirement analysis."""

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
    """Output model for task breakdown."""

    task_id: str
    title: str
    description: str
    assignee: str = "C"
    dependencies: List[str] = Field(default_factory=list)  # New: task dependencies


class TaskBreakdownOutput(BaseModel):
    """Output model for complete task breakdown."""

    tasks: List[TaskOutput]
    can_parallelize: bool = False  # New: whether tasks can run in parallel


class ReviewOutput(BaseModel):
    """Output model for code review."""

    approved: bool
    notes: str = ""
    issues: List[str] = Field(default_factory=list)  # New: specific issues to fix


class TestPlanOutput(BaseModel):
    """Output model for test plan."""

    blackbox_cases: List[TestCaseOutput] = Field(default_factory=list)
    whitebox_cases: List[TestCaseOutput] = Field(default_factory=list)
    verification_notes: str = ""


class TestExecutionOutput(BaseModel):
    """Output model for test execution."""

    passed: bool
    missing_coverage: List[str] = Field(default_factory=list)
    notes: str = ""


class TaskClosureOutput(BaseModel):
    """Output model for task closure."""

    commit_message: str
    status_summary: str = ""


# Type alias for progress callback
ProgressCallback = Callable[[str, int, int], None]


class CrewWorkflow:
    """Enhanced workflow with retry, tools, memory, and progress tracking."""

    TOTAL_STEPS = 7  # Number of workflow steps

    def __init__(
        self,
        tasks_path: str,
        test_cases_path: str,
        prompt_fn: Optional[Callable[[str], str]] = None,
        test_runner: Optional[Callable[[], bool]] = None,
        llm_config: Optional[LLMConfig] = None,
        progress_callback: Optional[ProgressCallback] = None,
        on_complete: Optional[Callable[[WorkflowResult], None]] = None,
        on_failure: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Initialize workflow.

        Args:
            tasks_path: Path to task storage file
            test_cases_path: Path to test case storage file
            prompt_fn: Function to prompt user for input
            test_runner: Function to run tests
            llm_config: LLM configuration
            progress_callback: Callback for progress updates (step_name, current, total)
            on_complete: Callback when workflow completes successfully
            on_failure: Callback when workflow fails
        """
        self.task_store = TaskStore(tasks_path)
        self.case_store = TestCaseStore(test_cases_path)
        self.task_tracker = TaskTrackerAgent(task_updater=self.task_store.update)
        self.prompt_fn = prompt_fn or (lambda msg: input(msg))
        self.test_runner = test_runner
        self.llm_config = llm_config or load_llm_config()
        self.progress_callback = progress_callback
        self.on_complete = on_complete
        self.on_failure = on_failure

        # Validate configuration
        try:
            validate_config(self.llm_config)
        except ConfigurationError as exc:
            log.error(f"Configuration error: {exc.message}")
            raise

    def _report_progress(self, step_name: str, current: int) -> None:
        """Report progress if callback is set."""
        if self.progress_callback:
            try:
                self.progress_callback(step_name, current, self.TOTAL_STEPS)
            except Exception as exc:
                log.warning(f"Progress callback failed: {exc}")

    def run(self, request: CrewRequest, auto_confirm: bool = False) -> WorkflowResult:
        """Run the complete workflow with retry and error handling.

        Args:
            request: User request to process
            auto_confirm: Skip user confirmation

        Returns:
            WorkflowResult: Final workflow result

        Raises:
            ConfigurationError: If configuration is invalid
            MaxRetriesExceededError: If maximum retries exceeded
        """
        log.info(f"CrewAI workflow started: {request.title}")

        try:
            if auto_confirm:
                request.confirmed = True

            # Build LLM with fallback support
            llm = self._build_llm_with_fallback(self.llm_config)
            if llm is None:
                raise ConfigurationError("Failed to initialize LLM with all providers")

            # Build memory if enabled
            memory = self._build_memory() if self.llm_config.enable_memory else None

            # Execute workflow with retry logic
            result = self._execute_workflow_with_retry(request, llm, memory, auto_confirm)

            # Call completion callback
            if self.on_complete:
                try:
                    self.on_complete(result)
                except Exception as exc:
                    log.warning(f"Completion callback failed: {exc}")

            return result

        except Exception as exc:
            log.error(f"Workflow failed: {exc}\n{traceback.format_exc()}")

            # Call failure callback
            if self.on_failure:
                try:
                    self.on_failure(exc)
                except Exception as callback_exc:
                    log.warning(f"Failure callback failed: {callback_exc}")

            # Re-raise with context
            if isinstance(exc, (ConfigurationError, MaxRetriesExceededError)):
                raise
            return WorkflowResult(False, f"Workflow failed: {exc}")

    def _execute_workflow_with_retry(
        self, request: CrewRequest, llm: Any, memory: Any, auto_confirm: bool
    ) -> WorkflowResult:
        """Execute workflow with retry logic for failed reviews."""
        max_retries = self.llm_config.max_retries
        retry_count = 0

        while retry_count <= max_retries:
            try:
                if retry_count > 0:
                    log.info(f"Retry attempt {retry_count}/{max_retries}")
                    time.sleep(self.llm_config.retry_delay)

                return self._execute_workflow(request, llm, memory, auto_confirm)

            except ReviewFailedError as exc:
                retry_count += 1
                if retry_count > max_retries:
                    raise MaxRetriesExceededError("review", max_retries) from exc

                log.warning(f"Review failed (attempt {retry_count}): {exc.notes}")
                log.info("Triggering code fix and re-review...")

                # In a full implementation, we would:
                # 1. Create a fix task based on review notes
                # 2. Re-run code agent with fix instructions
                # 3. Continue from review step
                # For now, we'll retry the entire workflow
                continue

            except TestExecutionError as exc:
                retry_count += 1
                if retry_count > max_retries:
                    raise MaxRetriesExceededError("test_execution", max_retries) from exc

                log.warning(f"Tests failed (attempt {retry_count}): {exc.message}")
                log.info("Analyzing test failures and retrying...")
                continue

        raise MaxRetriesExceededError("workflow", max_retries)

    def _execute_workflow(
        self, request: CrewRequest, llm: Any, memory: Any, auto_confirm: bool
    ) -> WorkflowResult:
        """Execute single workflow iteration."""
        # Step 1: Requirement Analysis
        self._report_progress("需求分析中...", 1)
        agents = self._build_agents(llm)
        tasks = self._build_tasks(agents, auto_confirm)

        crew = self._build_crew(agents, tasks, memory)

        inputs = {
            "request_type": request.request_type.value,
            "title": request.title,
            "details": request.details,
        }

        try:
            crew.kickoff(inputs=inputs)
        except Exception as exc:
            raise ConfigurationError(f"CrewAI kickoff failed: {exc}") from exc

        # Step 2: Process Analysis Output
        self._report_progress("处理需求分析结果...", 2)
        analysis_task = tasks[0]
        requirement = self._read_output(analysis_task, RequirementOutput)

        if requirement is None:
            return WorkflowResult(False, "Requirement analysis output missing")

        if auto_confirm:
            requirement.confirmed = True

        if not requirement.confirmed:
            return WorkflowResult(False, "Request not confirmed by user")

        # Check for conflicts
        req_type = requirement.request_type.strip().lower()
        existing_cases = self.case_store.load_existing(self.case_store.path)

        if self._detect_conflicts(requirement.title, existing_cases) or requirement.conflict:
            answer = self.prompt_fn(
                "Conflicting test cases detected. Type 'yes' to proceed, anything else to stop: "
            ).strip()
            if answer.lower() != "yes":
                return WorkflowResult(False, "Conflict detected with existing test cases")

        # Save initial test cases
        test_cases = self._convert_cases(requirement.blackbox_cases, scope="blackbox")
        if req_type == RequestType.OPTIMIZATION.value:
            log.info("Optimization request: skip blackbox test case updates")
            test_cases = []
        elif test_cases:
            self.case_store.write(test_cases)

        if req_type == RequestType.BUG.value and requirement.bug_gap:
            log.info(f"Bug analysis: {requirement.bug_gap}")
        if req_type == RequestType.OPTIMIZATION.value and requirement.optimization_scope:
            log.info(f"Optimization scope: {requirement.optimization_scope}")

        # Step 3: Task Breakdown
        self._report_progress("任务拆分中...", 3)
        architect_task = tasks[1]
        task_breakdown = self._read_output(architect_task, TaskBreakdownOutput)

        if task_breakdown is None:
            return WorkflowResult(False, "Task breakdown output missing")

        tasks_list = self._convert_tasks(task_breakdown.tasks)
        self.task_store.write(tasks_list)

        # Step 4: Code Implementation (already done by agent)
        self._report_progress("代码实现中...", 4)

        # Step 5: Code Review
        self._report_progress("代码审查中...", 5)
        review_task = tasks[3]
        review = self._read_output(review_task, ReviewOutput)

        if review is None or not review.approved:
            notes = review.notes if review else "Review output missing"
            raise ReviewFailedError(notes, {"tasks": [t.task_id for t in tasks_list]})

        # Step 6: Test Case Writing
        self._report_progress("编写测试用例...", 6)
        test_task = tasks[4]
        test_plan = self._read_output(test_task, TestPlanOutput)

        if test_plan:
            new_cases: List[TestCase] = []
            if req_type != RequestType.OPTIMIZATION.value:
                new_cases.extend(self._convert_cases(test_plan.blackbox_cases, scope="blackbox"))
            new_cases.extend(self._convert_cases(test_plan.whitebox_cases, scope="whitebox"))
            if new_cases:
                self.case_store.write(new_cases)
                test_cases.extend(new_cases)

        # Step 7: Test Execution
        self._report_progress("执行测试...", 7)
        exec_task = tasks[5]
        exec_result = self._read_output(exec_task, TestExecutionOutput)

        if exec_result is None:
            return WorkflowResult(False, "Test execution output missing", tasks=tasks_list)

        # Run actual tests if runner provided
        runner_ok = True
        if self.test_runner:
            runner_ok = self.test_runner()

        if not exec_result.passed or not runner_ok:
            raise TestExecutionError(
                "Tests failed",
                failures=exec_result.missing_coverage if exec_result else [],
            )

        # Step 8: Task Closure
        self.task_tracker.close_tasks(tasks_list)

        tracker_task = tasks[6]
        tracker_output = self._read_output(tracker_task, TaskClosureOutput)
        commit_message = (
            tracker_output.commit_message if tracker_output and tracker_output.commit_message else None
        )

        if not commit_message:
            commit_message = self.task_tracker.generate_commit_message(tasks_list)

        log.info(f"Workflow completed successfully: {commit_message}")
        return WorkflowResult(
            True, f"Workflow complete. Commit message: {commit_message}", tasks=tasks_list, tests_added=test_cases
        )

    def _build_llm_with_fallback(self, config: LLMConfig) -> Any:
        """Build LLM with fallback support."""
        providers = config.all_providers()

        for i, provider_config in enumerate(providers):
            try:
                if i == 0:
                    log.info(f"Initializing primary LLM: {provider_config.provider}/{provider_config.model}")
                else:
                    log.info(
                        f"Trying fallback LLM #{i}: {provider_config.provider}/{provider_config.model}"
                    )

                llm = self._build_llm(provider_config)
                if llm is not None:
                    log.info(f"Successfully initialized LLM: {provider_config.provider}")
                    return llm

            except Exception as exc:
                log.warning(f"Failed to initialize {provider_config.provider}: {exc}")
                if i == len(providers) - 1:
                    raise LLMProviderError(
                        provider_config.provider, "All LLM providers failed", {"error": str(exc)}
                    ) from exc
                continue

        return None

    def _build_llm(self, config: LLMProviderConfig) -> Any:
        """Build single LLM instance."""
        try:
            from crewai import LLM
        except ImportError:
            log.error("CrewAI is not installed. Please install: pip install crewai")
            return None

        model = self._normalize_model(config)
        params: Dict[str, Any] = {"model": model}

        if config.provider:
            params["provider"] = config.provider
            params["custom_llm_provider"] = config.provider
            if "/" in model and not model.startswith("minimax/"):
                params["model"] = model.split("/", 1)[1]

        credential = config.credential()  # Will raise ConfigurationError if not set
        if credential:
            # For API-key based providers the param name remains api_key.
            params["api_key"] = credential
            # For OAuth-style providers some SDKs accept access_token; set both for compatibility.
            if config.auth_mode == "oauth":
                params["access_token"] = credential
                params["auth_mode"] = "oauth"

        if config.base_url:
            params["base_url"] = config.base_url
            params["api_base"] = config.base_url

        if config.temperature is not None:
            params["temperature"] = config.temperature

        if config.max_tokens is not None:
            params["max_tokens"] = config.max_tokens

        if config.timeout:
            params["timeout"] = config.timeout

        return LLM(**params)

    @staticmethod
    def _normalize_model(config: LLMProviderConfig) -> str:
        """Normalize model name."""
        if "/" in config.model:
            return config.model
        if config.provider:
            return f"{config.provider}/{config.model}"
        return config.model

    def _build_memory(self) -> Any:
        """Build CrewAI memory system."""
        try:
            from crewai import Memory

            log.info("Initializing CrewAI memory system")
            return Memory(
                short_term_memory=True,  # Session memory
                long_term_memory=True,  # Cross-session memory
                entity_memory=True,  # Entity tracking (files, functions, etc.)
            )
        except ImportError:
            log.warning("CrewAI Memory not available, continuing without memory")
            return None
        except Exception as exc:
            log.warning(f"Failed to initialize memory: {exc}")
            return None

    def _build_agents(self, llm: Any) -> List[Any]:
        """Build all workflow agents with tools."""
        try:
            from crewai import Agent
        except ImportError:
            raise ConfigurationError("CrewAI is not installed")

        # Get tools
        safe_tools = get_safe_tools()  # Read-only tools for most agents
        code_tools = get_code_tools()  # Code manipulation tools for code agent
        all_tools = get_all_tools()  # All tools including git for tracker

        analysis_agent = Agent(
            role="需求分析Agent",
            goal="与用户沟通确认需求并产出黑盒测试用例",
            backstory="负责澄清需求，识别冲突，并明确需求类型与约束。",
            llm=llm,
            tools=safe_tools,
            verbose=True,
            allow_delegation=False,
        )

        architect_agent = Agent(
            role="代码架构师Agent",
            goal="拆分任务并分配给工程师",
            backstory="将需求转化为可执行任务并记录。",
            llm=llm,
            tools=safe_tools,
            verbose=True,
            allow_delegation=False,
        )

        code_agent = Agent(
            role="代码编写工程师Agent",
            goal="根据任务实现代码并说明变更",
            backstory="专注于实现需求，不偏离任务范围。拥有读写代码、搜索代码库的能力。",
            llm=llm,
            tools=code_tools,  # Code manipulation tools
            verbose=True,
            allow_delegation=False,
        )

        review_agent = Agent(
            role="Review工程师Agent",
            goal="Review实现并指出问题",
            backstory="关注风险、缺陷与遗漏并给出结论。",
            llm=llm,
            tools=safe_tools,
            verbose=True,
            allow_delegation=False,
        )

        test_agent = Agent(
            role="测试用例编写工程师Agent",
            goal="编写黑盒与白盒测试用例并验证单用例",
            backstory="确保测试覆盖需求与代码分支。",
            llm=llm,
            tools=safe_tools,
            verbose=True,
            allow_delegation=False,
        )

        exec_agent = Agent(
            role="测试用例执行Agent",
            goal="执行测试用例并评估完备性",
            backstory="运行测试并判断是否需要补充。",
            llm=llm,
            tools=code_tools,  # Can execute tests
            verbose=True,
            allow_delegation=False,
        )

        tracker_agent = Agent(
            role="任务跟踪Agent",
            goal="更新任务状态并生成提交信息",
            backstory="收尾任务，生成提交信息与下一步建议。",
            llm=llm,
            tools=all_tools,  # Has git tools
            verbose=True,
            allow_delegation=False,
        )

        return [
            analysis_agent,
            architect_agent,
            code_agent,
            review_agent,
            test_agent,
            exec_agent,
            tracker_agent,
        ]

    def _build_tasks(self, agents: List[Any], human_input: bool = True) -> List[Any]:
        """Build all workflow tasks."""
        try:
            from crewai import Task
        except ImportError:
            raise ConfigurationError("CrewAI is not installed")

        analysis_task = Task(
            description=(
                "你是需求分析Agent。结合用户需求{title}({request_type})进行澄清，必要时通过人类输入提问。"
                "request_type必须为new_requirement/bug/optimization之一。"
                "确认需求后输出JSON：request_type/title/details/confirmed/conflict/notes/bug_gap/"
                "optimization_scope/blackbox_cases。"
                "若是bug，说明黑盒还是白盒用例缺失；若是优化，说明仅允许内部逻辑与白盒用例变更。"
                "blackbox_cases需包含明确步骤与预期结果。"
                "使用read_file工具查看现有代码和测试用例。"
            ),
            expected_output="结构化JSON，包含需求确认与黑盒用例列表",
            agent=agents[0],
            human_input=human_input,
            output_json=RequirementOutput,
        )

        architect_task = Task(
            description=(
                "基于需求分析输出拆分任务，生成可执行任务列表并标注分配给C。"
                "输出JSON：tasks[{task_id,title,description,assignee,dependencies}]。"
                "如果任务之间有依赖关系，在dependencies中标注。"
                "使用search_files和read_file工具了解代码结构。"
            ),
            expected_output="结构化JSON任务拆分",
            agent=agents[1],
            context=[analysis_task],
            output_json=TaskBreakdownOutput,
        )

        code_task = Task(
            description=(
                "根据任务拆分结果实现代码变更，输出实现说明、涉及文件与关键逻辑。"
                "不偏离任务范围。"
                "使用read_file读取现有代码，使用write_file修改代码，使用search_code查找相关代码。"
                "实现完成后说明具体修改了哪些文件和关键变更点。"
            ),
            expected_output="实现说明与变更摘要",
            agent=agents[2],
            context=[architect_task],
        )

        review_task = Task(
            description=(
                "Review代码实现，判断是否通过并指出问题。输出JSON：approved/notes/issues。"
                "使用read_file工具查看修改后的代码。"
                "如果发现问题，在issues列表中列出具体需要修复的问题。"
            ),
            expected_output="结构化Review结论",
            agent=agents[3],
            context=[code_task],
            output_json=ReviewOutput,
        )

        test_task = Task(
            description=(
                "基于Review通过的实现编写测试用例：黑盒与白盒。黑盒需与docs记录一一对应，"
                "白盒覆盖代码分支。若为优化需求，黑盒用例不变，仅输出白盒用例。"
                "输出JSON：blackbox_cases/whitebox_cases/verification_notes。"
                "使用read_file查看实现代码以设计白盒测试用例。"
            ),
            expected_output="结构化测试用例列表",
            agent=agents[4],
            context=[review_task],
            output_json=TestPlanOutput,
        )

        exec_task = Task(
            description=(
                "执行全部测试用例并评估完备性。输出JSON：passed/missing_coverage/notes。"
                "使用execute_command工具运行测试命令（如pytest）。"
                "分析测试输出，判断是否通过，并识别缺失的覆盖领域。"
            ),
            expected_output="结构化测试执行结果",
            agent=agents[5],
            context=[test_task],
            output_json=TestExecutionOutput,
        )

        tracker_task = Task(
            description=(
                "更新任务状态，生成提交信息与下一步建议。输出JSON：commit_message/status_summary。"
                "使用git_operation工具查看git状态和diff。"
                "根据完成的任务生成有意义的commit message。"
            ),
            expected_output="结构化收尾信息",
            agent=agents[6],
            context=[exec_task],
            output_json=TaskClosureOutput,
        )

        return [
            analysis_task,
            architect_task,
            code_task,
            review_task,
            test_task,
            exec_task,
            tracker_task,
        ]

    def _build_crew(self, agents: List[Any], tasks: List[Any], memory: Any) -> Any:
        """Build crew with optional memory and process configuration."""
        try:
            from crewai import Crew, Process
        except ImportError:
            raise ConfigurationError("CrewAI is not installed")

        # Choose process based on configuration
        process = Process.hierarchical if self.llm_config.enable_parallel else Process.sequential

        crew_params = {
            "agents": agents,
            "tasks": tasks,
            "process": process,
            "verbose": True,
        }

        if memory:
            crew_params["memory"] = memory

        if process == Process.hierarchical:
            # Hierarchical process needs a manager LLM
            crew_params["manager_llm"] = self._build_llm(self.llm_config.primary)

        return Crew(**crew_params)

    @staticmethod
    def _read_output(task: Any, model_cls: type[BaseModel]) -> Optional[BaseModel]:
        """Read and parse task output."""
        if not task.output:
            return None

        if hasattr(task.output, "pydantic") and task.output.pydantic:
            return task.output.pydantic

        if hasattr(task.output, "json_dict") and task.output.json_dict:
            return model_cls(**task.output.json_dict)

        raw = getattr(task.output, "raw", None) or str(task.output)
        try:
            data = json.loads(raw)
            return model_cls(**data)
        except (json.JSONDecodeError, Exception) as exc:
            log.warning(f"Failed to parse task output: {exc}")
            return None

    @staticmethod
    def _detect_conflicts(title: str, existing_cases: List[TestCase]) -> bool:
        """Detect conflicts with existing test cases."""
        for case in existing_cases:
            if title.lower() in case.title.lower():
                return True
        return False

    @staticmethod
    def _convert_cases(cases: List[TestCaseOutput], scope: str) -> List[TestCase]:
        """Convert TestCaseOutput to TestCase."""
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
        """Convert TaskOutput to Task."""
        converted: List[Task] = []
        for task in tasks:
            metadata = {}
            if task.dependencies:
                metadata["dependencies"] = ",".join(task.dependencies)

            converted.append(
                Task(
                    task_id=task.task_id,
                    title=task.title,
                    description=task.description,
                    assignee=task.assignee,
                    status=TaskStatus.TODO,
                    metadata=metadata,
                )
            )
        return converted


def default_tasks_path() -> str:
    """Get default tasks path."""
    return os.path.join(os.getcwd(), "docs", "tasks.md")


def default_test_cases_path() -> str:
    """Get default test cases path."""
    return os.path.join(os.getcwd(), "docs", "test_cases_crew.md")
