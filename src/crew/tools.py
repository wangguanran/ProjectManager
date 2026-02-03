"""CrewAI tools for code manipulation and project operations."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.log_manager import log


class FileReadInput(BaseModel):
    """Input for file read tool."""

    filepath: str = Field(..., description="Path to the file to read")
    start_line: Optional[int] = Field(None, description="Starting line number (1-indexed)")
    end_line: Optional[int] = Field(None, description="Ending line number (1-indexed)")


class FileReadTool(BaseTool):
    """Tool for reading file contents."""

    name: str = "read_file"
    description: str = "Read contents of a file, optionally specifying line range"
    args_schema: type[BaseModel] = FileReadInput

    def _run(self, filepath: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        """Read file contents."""
        try:
            if not os.path.exists(filepath):
                return f"Error: File not found: {filepath}"

            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if start_line is not None or end_line is not None:
                start = (start_line - 1) if start_line else 0
                end = end_line if end_line else len(lines)
                lines = lines[start:end]

            content = "".join(lines)
            return f"File: {filepath}\n{'-' * 40}\n{content}"

        except Exception as exc:
            log.error(f"Error reading file {filepath}: {exc}")
            return f"Error reading file: {exc}"


class FileWriteInput(BaseModel):
    """Input for file write tool."""

    filepath: str = Field(..., description="Path to the file to write")
    content: str = Field(..., description="Content to write to the file")
    mode: str = Field("w", description="Write mode: 'w' (overwrite) or 'a' (append)")


class FileWriteTool(BaseTool):
    """Tool for writing to files."""

    name: str = "write_file"
    description: str = "Write content to a file (create or overwrite)"
    args_schema: type[BaseModel] = FileWriteInput

    def _run(self, filepath: str, content: str, mode: str = "w") -> str:
        """Write content to file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

            with open(filepath, mode, encoding="utf-8") as f:
                f.write(content)

            action = "appended to" if mode == "a" else "written to"
            log.info(f"Content {action} {filepath}")
            return f"Success: Content {action} {filepath}"

        except Exception as exc:
            log.error(f"Error writing to file {filepath}: {exc}")
            return f"Error writing file: {exc}"


class FileSearchInput(BaseModel):
    """Input for file search tool."""

    pattern: str = Field(..., description="Glob pattern to search for files (e.g., '**/*.py')")
    base_path: str = Field(".", description="Base directory to search from")


class FileSearchTool(BaseTool):
    """Tool for searching files by pattern."""

    name: str = "search_files"
    description: str = "Search for files matching a glob pattern"
    args_schema: type[BaseModel] = FileSearchInput

    def _run(self, pattern: str, base_path: str = ".") -> str:
        """Search for files matching pattern."""
        try:
            base = Path(base_path)
            matches = list(base.glob(pattern))

            if not matches:
                return f"No files found matching pattern: {pattern}"

            files = "\n".join(f"- {m.relative_to(base)}" for m in matches[:50])
            count = len(matches)
            truncated = " (showing first 50)" if count > 50 else ""
            return f"Found {count} files{truncated}:\n{files}"

        except Exception as exc:
            log.error(f"Error searching files: {exc}")
            return f"Error searching files: {exc}"


class CodeSearchInput(BaseModel):
    """Input for code search tool."""

    pattern: str = Field(..., description="Regex pattern to search for in code")
    file_pattern: Optional[str] = Field("**/*.py", description="File pattern to search within")
    base_path: str = Field(".", description="Base directory to search from")


class CodeSearchTool(BaseTool):
    """Tool for searching code content."""

    name: str = "search_code"
    description: str = "Search for code patterns using regex across files"
    args_schema: type[BaseModel] = CodeSearchInput

    def _run(self, pattern: str, file_pattern: str = "**/*.py", base_path: str = ".") -> str:
        """Search for code pattern."""
        try:
            # Use ripgrep if available, fallback to grep
            cmd = ["rg", "--json", pattern, "-g", file_pattern]
            try:
                result = subprocess.run(
                    cmd, cwd=base_path, capture_output=True, text=True, timeout=30, check=False
                )
                if result.returncode in [0, 1]:  # 0 = found, 1 = not found
                    # Parse ripgrep JSON output (simplified)
                    lines = result.stdout.strip().split("\n")[:20]
                    return f"Search results for '{pattern}':\n" + "\n".join(lines) if lines else "No matches found"
            except FileNotFoundError:
                # Fallback to basic grep
                cmd = ["grep", "-r", "-n", pattern, "--include", file_pattern.replace("**/", ""), base_path]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
                matches = result.stdout.strip().split("\n")[:20]
                return f"Found matches:\n" + "\n".join(matches) if matches and matches[0] else "No matches found"

        except subprocess.TimeoutExpired:
            return "Error: Search timed out"
        except Exception as exc:
            log.error(f"Error searching code: {exc}")
            return f"Error searching code: {exc}"


class GitOperationInput(BaseModel):
    """Input for git operations."""

    operation: str = Field(..., description="Git operation: status, diff, log, add, commit")
    args: List[str] = Field(default_factory=list, description="Additional arguments for the git command")


class GitOperationTool(BaseTool):
    """Tool for Git operations."""

    name: str = "git_operation"
    description: str = "Execute git operations (status, diff, log, add, commit)"
    args_schema: type[BaseModel] = GitOperationInput

    def _run(self, operation: str, args: Optional[List[str]] = None) -> str:
        """Execute git operation."""
        args = args or []
        try:
            # Safety check: prevent destructive operations
            dangerous_ops = ["push", "reset", "rebase", "force"]
            if any(danger in operation for danger in dangerous_ops):
                return f"Error: Operation '{operation}' is not allowed for safety reasons"

            cmd = ["git", operation] + args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)

            if result.returncode != 0:
                return f"Git {operation} failed:\n{result.stderr}"

            return f"Git {operation} output:\n{result.stdout}"

        except subprocess.TimeoutExpired:
            return f"Error: Git {operation} timed out"
        except Exception as exc:
            log.error(f"Error executing git {operation}: {exc}")
            return f"Error: {exc}"


class DirectoryListInput(BaseModel):
    """Input for directory listing."""

    path: str = Field(".", description="Directory path to list")
    recursive: bool = Field(False, description="List recursively")


class DirectoryListTool(BaseTool):
    """Tool for listing directory contents."""

    name: str = "list_directory"
    description: str = "List contents of a directory"
    args_schema: type[BaseModel] = DirectoryListInput

    def _run(self, path: str = ".", recursive: bool = False) -> str:
        """List directory contents."""
        try:
            target = Path(path)
            if not target.exists():
                return f"Error: Directory not found: {path}"

            if recursive:
                items = []
                for item in target.rglob("*"):
                    if item.is_file():
                        items.append(str(item.relative_to(target)))
                    if len(items) >= 100:
                        break
                result = "\n".join(f"- {item}" for item in items)
                return f"Contents of {path} (recursive, max 100):\n{result}"
            else:
                items = [item.name for item in target.iterdir()]
                result = "\n".join(f"- {item}" for item in sorted(items))
                return f"Contents of {path}:\n{result}"

        except Exception as exc:
            log.error(f"Error listing directory {path}: {exc}")
            return f"Error listing directory: {exc}"


class CommandExecutionInput(BaseModel):
    """Input for command execution."""

    command: str = Field(..., description="Command to execute")
    working_dir: str = Field(".", description="Working directory for command execution")


class CommandExecutionTool(BaseTool):
    """Tool for executing shell commands."""

    name: str = "execute_command"
    description: str = "Execute a shell command and return its output"
    args_schema: type[BaseModel] = CommandExecutionInput

    def _run(self, command: str, working_dir: str = ".") -> str:
        """Execute shell command."""
        try:
            # Safety check: prevent dangerous commands
            dangerous = ["rm -rf", "dd if=", "> /dev/", "mkfs", "format"]
            if any(danger in command for danger in dangerous):
                return f"Error: Command contains dangerous pattern: {command}"

            result = subprocess.run(
                command, shell=True, cwd=working_dir, capture_output=True, text=True, timeout=60, check=False
            )

            output = f"Command: {command}\n"
            output += f"Exit code: {result.returncode}\n"
            if result.stdout:
                output += f"Output:\n{result.stdout}\n"
            if result.stderr:
                output += f"Errors:\n{result.stderr}\n"

            return output

        except subprocess.TimeoutExpired:
            return f"Error: Command timed out: {command}"
        except Exception as exc:
            log.error(f"Error executing command {command}: {exc}")
            return f"Error executing command: {exc}"


def get_all_tools() -> List[BaseTool]:
    """Get all available tools for agents."""
    return [
        FileReadTool(),
        FileWriteTool(),
        FileSearchTool(),
        CodeSearchTool(),
        GitOperationTool(),
        DirectoryListTool(),
        CommandExecutionTool(),
    ]


def get_code_tools() -> List[BaseTool]:
    """Get tools specifically for code manipulation."""
    return [
        FileReadTool(),
        FileWriteTool(),
        FileSearchTool(),
        CodeSearchTool(),
        DirectoryListTool(),
    ]


def get_git_tools() -> List[BaseTool]:
    """Get tools for Git operations."""
    return [
        GitOperationTool(),
    ]


def get_safe_tools() -> List[BaseTool]:
    """Get read-only safe tools."""
    return [
        FileReadTool(),
        FileSearchTool(),
        CodeSearchTool(),
        DirectoryListTool(),
    ]


__all__ = [
    "FileReadTool",
    "FileWriteTool",
    "FileSearchTool",
    "CodeSearchTool",
    "GitOperationTool",
    "DirectoryListTool",
    "CommandExecutionTool",
    "get_all_tools",
    "get_code_tools",
    "get_git_tools",
    "get_safe_tools",
]
