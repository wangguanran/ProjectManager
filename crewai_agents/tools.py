#!/usr/bin/env python3
"""
Tools for CrewAI Agents:
- file operations
- git helpers
- running tests / lint
- simple task list management
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from typing import Any, Dict, List


class FileUtils:
    """文件操作工具"""

    @staticmethod
    def read_file(file_path: str) -> str:
        """读取文件内容"""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def write_file(file_path: str, content: str) -> bool:
        """写入文件"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    @staticmethod
    def append_file(file_path: str, content: str) -> bool:
        """追加文件"""
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(content)
        return True

    @staticmethod
    def file_exists(file_path: str) -> bool:
        """检查文件是否存在"""
        return os.path.exists(file_path)


class GitUtils:
    """Git 操作工具"""

    @staticmethod
    def run_git_command(command: List[str], cwd: str = None) -> Dict[str, Any]:
        """执行 Git 命令"""
        try:
            result = subprocess.run(
                ["git"] + command,
                cwd=cwd or os.getcwd(),
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except (OSError, subprocess.SubprocessError) as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_current_branch(cwd: str = None) -> str:
        """获取当前分支"""
        result = GitUtils.run_git_command(["branch", "--show-current"], cwd)
        if result["success"]:
            return result["stdout"].strip()
        return "master"

    @staticmethod
    def stage_all(cwd: str = None) -> bool:
        """暂存所有文件"""
        result = GitUtils.run_git_command(["add", "."], cwd)
        return result["success"]

    @staticmethod
    def commit(message: str, cwd: str = None) -> bool:
        """提交代码"""
        result = GitUtils.run_git_command(["commit", "-m", message], cwd)
        return result["success"]

    @staticmethod
    def push(cwd: str = None) -> bool:
        """推送代码"""
        branch = GitUtils.get_current_branch(cwd)
        result = GitUtils.run_git_command(["push", "origin", branch], cwd)
        return result["success"]

    @staticmethod
    def generate_commit_message(tasks: List[Dict]) -> str:
        """生成 commit message"""
        if not tasks:
            return "chore: 更新项目"

        # 按类型分组
        types = {"feat": [], "fix": [], "docs": [], "refactor": [], "test": [], "chore": []}

        for task in tasks:
            title = task.get("title", "")
            # 简单分类
            if "删除" in title or "移除" in title:
                types["fix"].append(title)
            elif "测试" in title:
                types["test"].append(title)
            elif "文档" in title:
                types["docs"].append(title)
            else:
                types["feat"].append(title)

        # 生成 message
        lines = []
        for type_name, items in types.items():
            if items:
                scope = "project"
                subjects = "; ".join(items[:3])  # 最多3个
                lines.append(f"{type_name}({scope}): {subjects}")

        return "\n".join(lines) if lines else "chore: 更新项目"


class TestUtils:
    """测试工具"""

    @staticmethod
    def run_pytest(cwd: str = None, verbose: bool = True) -> Dict[str, Any]:
        """运行 pytest"""
        cmd = ["python", "-m", "pytest", "-v", "--tb=short"]
        if not verbose:
            cmd.remove("-v")

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or os.getcwd(),
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout + result.stderr,
                "returncode": result.returncode,
            }
        except (OSError, subprocess.SubprocessError) as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def check_code_quality(cwd: str = None) -> Dict[str, Any]:
        """检查代码质量 (pylint)"""
        try:
            result = subprocess.run(
                ["python", "-m", "pylint", "src/", "--output-format=text"],
                cwd=cwd or os.getcwd(),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout + result.stderr,
                "score": TestUtils._extract_pylint_score(result.stdout),
            }
        except (OSError, subprocess.SubprocessError) as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _extract_pylint_score(output: str) -> float:
        """提取 pylint 分数"""
        for line in output.split("\n"):
            if "Your code has been rated at" in line:
                try:
                    return float(line.split("at")[1].split("/")[0].strip())
                except (IndexError, ValueError):
                    continue
        return 0.0


class TaskManager:
    """任务管理工具"""

    def __init__(self, tasks_file: str):
        self.tasks_file = tasks_file

    def add_task(self, task: Dict) -> bool:
        """添加任务"""
        content = FileUtils.read_file(self.tasks_file)

        # 解析现有任务
        tasks = self._parse_tasks(content)
        tasks.append(task)

        # 重新生成内容
        new_content = self._generate_tasks_md(tasks)
        FileUtils.write_file(self.tasks_file, new_content)
        return True

    def update_task_status(self, task_id: str, status: str) -> bool:
        """更新任务状态"""
        content = FileUtils.read_file(self.tasks_file)
        tasks = self._parse_tasks(content)

        for task in tasks:
            if task.get("id") == task_id:
                task["status"] = status
                task["updated_at"] = datetime.now().isoformat()
                if status == "done":
                    task["完成时间"] = datetime.now().isoformat()
                break

        new_content = self._generate_tasks_md(tasks)
        FileUtils.write_file(self.tasks_file, new_content)
        return True

    def get_pending_tasks(self) -> List[Dict]:
        """获取待处理任务"""
        content = FileUtils.read_file(self.tasks_file)
        tasks = self._parse_tasks(content)
        return [t for t in tasks if t.get("status") == "pending"]

    def _parse_tasks(self, content: str) -> List[Dict[str, str]]:
        """解析任务列表"""
        tasks: List[Dict[str, str]] = []
        # 简单解析 - 实际应该用更健壮的方法
        lines = content.split("\n")
        current_task: Dict[str, str] = {}
        has_task = False

        for line in lines:
            if line.startswith("### 任务 ID:"):
                if has_task:
                    tasks.append(current_task)
                current_task = {"id": line.split(":")[1].strip()}
                has_task = True
            elif has_task and ":" in line:
                key = line.split(":")[0].strip().replace("**", "")
                value = line.split(":")[1].strip().replace("**", "")
                current_task[key] = value

        if has_task:
            tasks.append(current_task)

        return tasks

    def _generate_tasks_md(self, tasks: List[Dict]) -> str:
        """生成任务 Markdown"""
        lines = [
            "# 任务列表\n",
            "> 此文档由架构师 Agent 自动生成和维护\n",
            f"- **最后更新**: {datetime.now().isoformat()}\n",
            "\n## 任务列表\n",
        ]

        for task in tasks:
            lines.append(f"### 任务 ID: {task.get('id', 'TASK-000')}")
            lines.append(f"- **标题**: {task.get('标题', '')}")
            lines.append(f"- **描述**: {task.get('描述', '')}")
            lines.append(f"- **状态**: {task.get('status', 'pending')}")
            lines.append(f"- **优先级**: {task.get('优先级', 'medium')}")
            lines.append(f"- **负责人**: {task.get('负责人', '')}")
            lines.append(f"- **创建时间**: {task.get('创建时间', datetime.now().isoformat())}")
            lines.append("")

        return "\n".join(lines)
