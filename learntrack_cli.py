"""LearnTrack command-line interface and input validation.

This module owns the menu and user input only. Task data, persistence, CRUD,
filtering, and statistics stay in the manager implementation passed to
:func:`run_cli`. The expected interface is documented by ``TaskManagerPort``
and ``TaskRecord`` below.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Protocol
from unicodedata import east_asian_width


STATUSES = ("To Do", "In Progress", "Completed")

# Accept both ASCII and full-width commas so IME input splits subtasks too.
SUBTASK_SEPARATORS = re.compile(r"[,，]")


def split_subtasks(text: str) -> list[str]:
    """Split a subtask line on ASCII or full-width commas, dropping blanks."""
    return [item.strip() for item in SUBTASK_SEPARATORS.split(text) if item.strip()]


class TaskRecord(Protocol):
    task_id: str
    title: str
    course: str
    due_date: str
    priority: int
    status: str
    subtasks: list[str]


class TaskManagerPort(Protocol):
    """Interface expected from the manager implementation."""

    def add_task(
        self,
        title: str,
        course: str,
        due_date: str = "",
        priority: int = 3,
        subtasks: list[str] | None = None,
    ) -> TaskRecord: ...

    def get_task(self, task_id: str) -> TaskRecord: ...

    def get_tasks(self) -> list[TaskRecord]: ...

    def update_task(self, task_id: str, **updates: Any) -> TaskRecord: ...

    def delete_task(self, task_id: str) -> TaskRecord: ...

    def filter_tasks(
        self,
        course: str | None = None,
        status: str | None = None,
        overdue_only: bool = False,
    ) -> list[TaskRecord]: ...

    def statistics(self) -> dict[str, int | float]: ...


class LearnTrackCLI:
    """Menu and input validation layer; delegates task work to the manager."""

    def __init__(self, manager: TaskManagerPort) -> None:
        self.manager = manager

    def run(self) -> None:
        print("\nLearnTrack - Personal Learning Task Manager")
        while True:
            print(
                "\n1. Add task\n"
                "2. List tasks\n"
                "3. View task details\n"
                "4. Update task\n"
                "5. Delete task\n"
                "6. Filter tasks\n"
                "7. View statistics\n"
                "0. Exit"
            )
            choice = self._choice("Choose an option: ", {"0", "1", "2", "3", "4", "5", "6", "7"})
            try:
                if choice == "1":
                    self._add_task()
                elif choice == "2":
                    self._list_tasks(self.manager.get_tasks())
                elif choice == "3":
                    self._view_task()
                elif choice == "4":
                    self._update_task()
                elif choice == "5":
                    self._delete_task()
                elif choice == "6":
                    self._filter_tasks()
                elif choice == "7":
                    self._show_statistics()
                else:
                    print("Goodbye.")
                    return
            except ValueError as exc:
                print(f"Unable to complete that action: {exc}")

    def _add_task(self) -> None:
        title = self._non_empty("Task title: ")
        course = self._non_empty("Course: ")
        due_date = self._date_input("Due date (YYYY-MM-DD, blank for none): ", allow_blank=True)
        priority = self._priority_input()
        subtasks = split_subtasks(
            input("Subtasks (comma-separated, blank for none): ").strip())
        task = self.manager.add_task(title, course, due_date, priority, subtasks)
        if getattr(self.manager, "last_save_failed", False):
            print(f"Task '{task.title}' is kept in memory but could not be saved; "
                  "check the task file permissions and retry.")
        else:
            print(f"Added task {task.task_id}: {task.title}")

    def _view_task(self) -> None:
        task_id = self._task_id_input()
        if task_id is None:
            return
        self._print_details(self.manager.get_task(task_id))

    def _update_task(self) -> None:
        task_id = self._task_id_input()
        if task_id is None:
            return
        task = self.manager.get_task(task_id)
        print(f"Updating {task.title} ({task.task_id})")
        print("1. Title  2. Course  3. Due date  4. Priority  5. Status  6. Subtasks")
        field_choice = self._choice("Choose a field: ", {"1", "2", "3", "4", "5", "6"})
        if field_choice == "1":
            updates = {"title": self._non_empty("New title: ")}
        elif field_choice == "2":
            updates = {"course": self._non_empty("New course: ")}
        elif field_choice == "3":
            updates = {"due_date": self._date_input("New due date (YYYY-MM-DD, blank to clear): ", True)}
        elif field_choice == "4":
            updates = {"priority": self._priority_input()}
        elif field_choice == "5":
            updates = {"status": self._status_input()}
        else:
            text = input("New subtasks (comma-separated, blank to clear): ").strip()
            updates = {"subtasks": split_subtasks(text)}
        updated = self.manager.update_task(task.task_id, **updates)
        if getattr(self.manager, "last_save_failed", False):
            print("Update is kept in memory but could not be saved.")
        else:
            print(f"Updated task {updated.task_id}.")

    def _delete_task(self) -> None:
        task_id = self._task_id_input()
        if task_id is None:
            return
        task = self.manager.get_task(task_id)
        answer = input(f"Delete '{task.title}'? (y/N): ").strip().casefold()
        if answer == "y":
            self.manager.delete_task(task.task_id)
            if getattr(self.manager, "last_save_failed", False):
                print("Deletion is kept in memory but could not be saved.")
            else:
                print("Task deleted.")
        else:
            print("Delete cancelled.")

    def _filter_tasks(self) -> None:
        print("1. By course  2. By status  3. Overdue tasks")
        filter_choice = self._choice("Choose a filter: ", {"1", "2", "3"})
        if filter_choice == "1":
            results = self.manager.filter_tasks(course=self._non_empty("Course: "))
        elif filter_choice == "2":
            results = self.manager.filter_tasks(status=self._status_input())
        else:
            results = self.manager.filter_tasks(overdue_only=True)
        self._list_tasks(results)

    # ------------------------------------------------------- display width

    @staticmethod
    def _cells(text: str) -> int:
        """Terminal cells of ``text``; East-Asian wide/full-width chars take two."""
        return sum(2 if east_asian_width(char) in "WF" else 1 for char in text)

    @classmethod
    def _pad(cls, text: str, width: int) -> str:
        """Pad to ``width`` terminal cells."""
        return text + " " * max(0, width - cls._cells(text))

    @classmethod
    def _fit(cls, text: str, width: int) -> str:
        """Truncate ``text`` to at most ``width`` terminal cells."""
        if cls._cells(text) <= width:
            return text
        kept = 0
        for index, char in enumerate(text):
            kept += 2 if east_asian_width(char) in "WF" else 1
            if kept > width:
                return text[:index]
        return text

    def _list_tasks(self, tasks: list[TaskRecord]) -> None:
        if not tasks:
            print("No tasks to show.")
            return
        # Widths follow the identifiers and course names the manager supplies
        # and are measured in terminal cells, so CJK courses keep the columns
        # aligned.
        id_width = max(8, *(self._cells(task.task_id) for task in tasks))
        due_width = max(11, *(self._cells(task.due_date or "No date") for task in tasks))
        course_width = min(max(18, *(self._cells(task.course) for task in tasks)), 28)
        header = " ".join((
            self._pad("ID", id_width),
            self._pad("Due date", due_width),
            self._pad("P", 2),
            self._pad("Status", 12),
            self._pad("Course", course_width),
            "Title",
        ))
        print(f"\n{header}")
        print("-" * self._cells(header))
        for task in tasks:
            due = task.due_date or "No date"
            print(" ".join((
                self._pad(task.task_id, id_width),
                self._pad(due, due_width),
                self._pad(str(task.priority), 2),
                self._pad(task.status, 12),
                self._pad(self._fit(task.course, course_width), course_width),
                task.title,
            )))

    @staticmethod
    def _print_details(task: TaskRecord) -> None:
        print(f"\nID: {task.task_id}")
        print(f"Title: {task.title}")
        print(f"Course: {task.course}")
        print(f"Due date: {task.due_date or 'Not set'}")
        print(f"Priority: {task.priority}")
        print(f"Status: {task.status}")
        print("Subtasks:")
        if task.subtasks:
            for index, subtask in enumerate(task.subtasks, start=1):
                print(f"  {index}. {subtask}")
        else:
            print("  None")

    def _show_statistics(self) -> None:
        stats = self.manager.statistics()
        print("\nTask statistics")
        print(f"Total tasks: {stats['total']}")
        print(f"To Do: {stats['to_do']}")
        print(f"In Progress: {stats['in_progress']}")
        print(f"Completed: {stats['completed']}")
        print(f"Overdue: {stats['overdue']}")
        print(f"Completion rate: {stats['completion_rate']}%")

    @staticmethod
    def _choice(prompt: str, allowed: set[str]) -> str:
        while True:
            value = input(prompt).strip()
            if value in allowed:
                return value
            print(f"Please enter one of: {', '.join(sorted(allowed))}.")

    @staticmethod
    def _non_empty(prompt: str) -> str:
        while True:
            value = input(prompt).strip()
            if value:
                return value
            print("This field cannot be empty.")

    @staticmethod
    def _date_input(prompt: str, allow_blank: bool) -> str:
        while True:
            value = input(prompt).strip()
            if not value and allow_blank:
                return ""
            try:
                parsed_date = date.fromisoformat(value)
                if parsed_date.isoformat() != value:
                    raise ValueError
                return value
            except ValueError:
                print("Enter a valid date in YYYY-MM-DD format, or leave it blank if allowed.")

    @staticmethod
    def _priority_input() -> int:
        while True:
            value = input("Priority (1 highest - 4 lowest): ").strip()
            # isdecimal() accepts only characters int() can convert, so
            # superscript digits such as "²" are rejected here.
            if value.isdecimal() and int(value) in {1, 2, 3, 4}:
                return int(value)
            print("Priority must be 1, 2, 3, or 4.")

    @staticmethod
    def _status_input() -> str:
        # Derive both the legend and the mapping from STATUSES so they cannot
        # drift apart.
        labels = ("1", "2", "3")
        choice_to_status = dict(zip(labels, STATUSES))
        print("  ".join(f"{key}. {STATUSES[index]}"
                        for index, key in enumerate(labels)))
        while True:
            value = input("Status: ").strip()
            if value in choice_to_status:
                return choice_to_status[value]
            print("Choose 1, 2, or 3.")

    def _task_id_input(self) -> str | None:
        """Prompt for a task ID; return None when the user cancels with 0."""
        while True:
            task_id = input("Task ID (0 to return): ").strip()
            if task_id == "0":
                return None
            try:
                self.manager.get_task(task_id)
                return task_id
            except ValueError as exc:
                print(exc)


def run_cli(task_manager: TaskManagerPort) -> None:
    """Entry point called by the application after it builds the manager."""
    try:
        LearnTrackCLI(task_manager).run()
    except (EOFError, KeyboardInterrupt):
        print("\nLearnTrack closed.")


if __name__ == "__main__":
    from json_storage import create_manager

    # An unreadable store must produce a friendly message and exit code
    # instead of surfacing a raw traceback.
    try:
        manager = create_manager()
    except OSError as exc:
        print(f"LearnTrack cannot start: the task file is unreadable ({exc})")
        print("Close the program holding it, or fix/remove tasks.json, then retry.")
        raise SystemExit(1)
    run_cli(manager)
