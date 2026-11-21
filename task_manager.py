"""In-memory business layer for LearnTrack, matching the CLI manager protocol.

Tasks are kept in a dictionary keyed by task ID. Every task handed back to a
caller is an independent snapshot, so in-place edits cannot corrupt the
store. This module performs no file I/O; the storage layer serializes the
snapshots returned by :meth:`get_tasks`.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable
from uuid import uuid4

from task import Task


class TaskManager:
    """Validate and coordinate the stored tasks."""

    def __init__(self, tasks: Iterable[Task] | None = None) -> None:
        self._tasks: dict[str, Task] = {}
        for task in tasks if tasks is not None else ():
            if not isinstance(task, Task):
                raise ValueError("Initial tasks must contain Task objects")
            snapshot = self._copy(task)
            if snapshot.task_id in self._tasks:
                raise ValueError(f"Duplicate task ID: {snapshot.task_id}")
            self._tasks[snapshot.task_id] = snapshot

    @staticmethod
    def _copy(task: Task) -> Task:
        return Task.from_dict(task.to_dict())

    def _find(self, task_id: str) -> Task:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        if task_id not in self._tasks:
            raise ValueError(f"Task not found: {task_id}")
        return self._tasks[task_id]

    def add_task(
        self, title: str, course: str, due_date: str = "",
        priority: int = 3, subtasks: list[str] | None = None,
    ) -> Task:
        task_id = uuid4().hex
        while task_id in self._tasks:
            task_id = uuid4().hex
        task = Task(task_id, title, course, due_date, priority,
                    subtasks=[] if subtasks is None else subtasks)
        self._tasks[task_id] = task
        return self._copy(task)

    def get_task(self, task_id: str) -> Task:
        return self._copy(self._find(task_id))

    def get_tasks(self) -> list[Task]:
        """List tasks ordered by deadline (undated last), priority, then ID."""
        ordered = sorted(self._tasks.values(), key=lambda task: (
            not bool(task.due_date), task.due_date, task.priority, task.task_id
        ))
        return [self._copy(task) for task in ordered]

    def update_task(self, task_id: str, **updates: Any) -> Task:
        """Validate all changes before committing; the ID cannot be changed."""
        task = self._find(task_id)
        allowed = {"title", "course", "due_date", "priority", "status", "subtasks"}
        if set(updates) - allowed:
            raise ValueError("Updates contain unsupported fields")
        data = task.to_dict()
        data.update(updates)
        updated = Task.from_dict(data)
        self._tasks[task_id] = updated
        return self._copy(updated)

    def delete_task(self, task_id: str) -> Task:
        snapshot = self._copy(self._find(task_id))
        del self._tasks[task_id]
        return snapshot

    @staticmethod
    def _overdue(task: Task, today: str) -> bool:
        return bool(task.due_date) and task.due_date < today and task.status != "Completed"

    def filter_tasks(
        self, course: str | None = None, status: str | None = None,
        overdue_only: bool = False,
    ) -> list[Task]:
        """Filter by exact course, exact status, and/or overdue state (AND)."""
        if course is not None:
            Task._check("course", course)
        if status is not None:
            Task._check("status", status)
        if type(overdue_only) is not bool:
            raise ValueError("overdue_only must be a boolean")
        today = date.today().isoformat()
        return [task for task in self.get_tasks()
                if (course is None or task.course == course)
                and (status is None or task.status == status)
                and (not overdue_only or self._overdue(task, today))]

    def statistics(self) -> dict[str, int | float]:
        """Return counts by status, overdue count, and completion rate."""
        tasks = list(self._tasks.values())
        total = len(tasks)
        completed = sum(task.status == "Completed" for task in tasks)
        today = date.today().isoformat()
        return {
            "total": total,
            "to_do": sum(task.status == "To Do" for task in tasks),
            "in_progress": sum(task.status == "In Progress" for task in tasks),
            "completed": completed,
            "overdue": sum(self._overdue(task, today) for task in tasks),
            "completion_rate": round(completed / total * 100, 2) if total else 0.0,
        }
