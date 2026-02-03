"""Enhanced storage backends for tasks and test cases using SQLite."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.log_manager import log

from .models import Task, TaskStatus, TestCase


class SQLiteTestCaseStore:
    """SQLite-based test case storage with deduplication and versioning."""

    def __init__(self, db_path: str):
        """Initialize SQLite store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure database and tables exist."""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_cases (
                    case_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    case_type TEXT NOT NULL,
                    steps TEXT NOT NULL,
                    expected TEXT NOT NULL,
                    priority TEXT DEFAULT 'P1',
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    version INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_test_cases_scope ON test_cases(scope)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_test_cases_type ON test_cases(case_type)
            """)
            conn.commit()
        finally:
            conn.close()

    def write(self, test_cases: List[TestCase], deduplicate: bool = True) -> int:
        """Write test cases to database.

        Args:
            test_cases: List of test cases to write
            deduplicate: If True, update existing cases instead of failing

        Returns:
            Number of test cases written
        """
        conn = sqlite3.connect(self.db_path)
        written = 0

        try:
            for case in test_cases:
                steps_json = json.dumps(case.steps)
                expected_json = json.dumps(case.expected)
                now = datetime.utcnow().isoformat()

                if deduplicate and self._exists(case.case_id, conn):
                    # Update existing case
                    conn.execute(
                        """
                        UPDATE test_cases
                        SET title = ?, scope = ?, case_type = ?, steps = ?, expected = ?,
                            priority = ?, updated_at = ?, version = version + 1
                        WHERE case_id = ?
                    """,
                        (
                            case.title,
                            case.scope,
                            case.case_type,
                            steps_json,
                            expected_json,
                            case.priority,
                            now,
                            case.case_id,
                        ),
                    )
                    log.info(f"Updated test case: {case.case_id}")
                else:
                    # Insert new case
                    conn.execute(
                        """
                        INSERT INTO test_cases 
                        (case_id, title, scope, case_type, steps, expected, priority, created_at, updated_at, version)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                        (
                            case.case_id,
                            case.title,
                            case.scope,
                            case.case_type,
                            steps_json,
                            expected_json,
                            case.priority,
                            now,
                            now,
                        ),
                    )
                    log.info(f"Inserted test case: {case.case_id}")

                written += 1

            conn.commit()
        except sqlite3.IntegrityError as exc:
            log.error(f"Database integrity error: {exc}")
            conn.rollback()
            raise
        finally:
            conn.close()

        return written

    def load_all(self) -> List[TestCase]:
        """Load all test cases from database."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                SELECT case_id, title, scope, case_type, steps, expected, priority
                FROM test_cases
                ORDER BY created_at DESC
            """)

            cases = []
            for row in cursor.fetchall():
                cases.append(
                    TestCase(
                        case_id=row[0],
                        title=row[1],
                        scope=row[2],
                        case_type=row[3],
                        steps=json.loads(row[4]),
                        expected=json.loads(row[5]),
                        priority=row[6],
                    )
                )
            return cases
        finally:
            conn.close()

    def load_by_scope(self, scope: str) -> List[TestCase]:
        """Load test cases by scope (blackbox/whitebox)."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT case_id, title, scope, case_type, steps, expected, priority
                FROM test_cases
                WHERE scope = ?
                ORDER BY created_at DESC
            """,
                (scope,),
            )

            cases = []
            for row in cursor.fetchall():
                cases.append(
                    TestCase(
                        case_id=row[0],
                        title=row[1],
                        scope=row[2],
                        case_type=row[3],
                        steps=json.loads(row[4]),
                        expected=json.loads(row[5]),
                        priority=row[6],
                    )
                )
            return cases
        finally:
            conn.close()

    def get(self, case_id: str) -> Optional[TestCase]:
        """Get a specific test case by ID."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT case_id, title, scope, case_type, steps, expected, priority
                FROM test_cases
                WHERE case_id = ?
            """,
                (case_id,),
            )

            row = cursor.fetchone()
            if row:
                return TestCase(
                    case_id=row[0],
                    title=row[1],
                    scope=row[2],
                    case_type=row[3],
                    steps=json.loads(row[4]),
                    expected=json.loads(row[5]),
                    priority=row[6],
                )
            return None
        finally:
            conn.close()

    def delete(self, case_id: str) -> bool:
        """Delete a test case."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("DELETE FROM test_cases WHERE case_id = ?", (case_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def export_to_markdown(self, output_path: str) -> None:
        """Export test cases to Markdown format."""
        cases = self.load_all()

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# Test Cases\n\n")

            for case in cases:
                f.write(f"## {case.case_id} {case.title}\n")
                f.write(f"- Scope: {case.scope}\n")
                f.write(f"- Type: {case.case_type}\n")
                f.write(f"- Priority: {case.priority}\n")
                f.write("- Steps:\n")
                for step in case.steps:
                    f.write(f"  - {step}\n")
                f.write("- Expected:\n")
                for expected in case.expected:
                    f.write(f"  - {expected}\n")
                f.write("\n")

        log.info(f"Exported {len(cases)} test cases to {output_path}")

    def _exists(self, case_id: str, conn: Optional[sqlite3.Connection] = None) -> bool:
        """Check if a test case exists."""
        should_close = conn is None
        if conn is None:
            conn = sqlite3.connect(self.db_path)

        try:
            cursor = conn.execute("SELECT 1 FROM test_cases WHERE case_id = ?", (case_id,))
            return cursor.fetchone() is not None
        finally:
            if should_close:
                conn.close()


class SQLiteTaskStore:
    """SQLite-based task storage with audit trail."""

    def __init__(self, db_path: str):
        """Initialize SQLite task store."""
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure database and tables exist."""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    assignee TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)
            """)
            conn.commit()
        finally:
            conn.close()

    def write(self, tasks: List[Task]) -> None:
        """Write tasks to database."""
        conn = sqlite3.connect(self.db_path)
        try:
            for task in tasks:
                metadata_json = json.dumps(task.metadata)

                conn.execute(
                    """
                    INSERT OR REPLACE INTO tasks
                    (task_id, title, description, assignee, status, created_at, updated_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        task.task_id,
                        task.title,
                        task.description,
                        task.assignee,
                        task.status.value,
                        task.created_at,
                        task.updated_at,
                        metadata_json,
                    ),
                )

                # Add to history
                conn.execute(
                    """
                    INSERT INTO task_history (task_id, status, timestamp, notes)
                    VALUES (?, ?, ?, ?)
                """,
                    (task.task_id, task.status.value, datetime.utcnow().isoformat(), f"Task status: {task.status.value}"),
                )

            conn.commit()
        finally:
            conn.close()

    def update(self, tasks: List[Task]) -> None:
        """Update existing tasks."""
        self.write(tasks)  # Same as write with INSERT OR REPLACE

    def load_all(self) -> List[Task]:
        """Load all tasks."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                SELECT task_id, title, description, assignee, status, created_at, updated_at, metadata
                FROM tasks
                ORDER BY created_at DESC
            """)

            tasks = []
            for row in cursor.fetchall():
                metadata = json.loads(row[7]) if row[7] else {}
                tasks.append(
                    Task(
                        task_id=row[0],
                        title=row[1],
                        description=row[2],
                        assignee=row[3],
                        status=TaskStatus(row[4]),
                        created_at=row[5],
                        updated_at=row[6],
                        metadata=metadata,
                    )
                )
            return tasks
        finally:
            conn.close()

    def get_history(self, task_id: str) -> List[dict]:
        """Get status history for a task."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT status, timestamp, notes
                FROM task_history
                WHERE task_id = ?
                ORDER BY timestamp ASC
            """,
                (task_id,),
            )

            history = []
            for row in cursor.fetchall():
                history.append({"status": row[0], "timestamp": row[1], "notes": row[2]})
            return history
        finally:
            conn.close()


__all__ = ["SQLiteTestCaseStore", "SQLiteTaskStore"]
