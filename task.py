"""LearnTrack task entity (Python 3.10+, standard library only).

TaskManager supplies task_id and owns ID uniqueness. Dates use YYYY-MM-DD,
with an empty string meaning no deadline. Priority 1 is highest, 4 lowest.
Storage can use to_dict()/from_dict() or to_json()/from_json().
All validation failures raise ValueError, matching the CLI error boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date
import json
from typing import Any, ClassVar


@dataclass
class Task:
    """TaskRecord-compatible entity; no UI, storage, or manager dependencies.

    Assignments are validated before changing a field. Subtask lists are copied
    on assignment and export. In-place list edits are checked by validate() and
    again before serialization; callers should assign a new list for immediate
    validation of edits.
    """

    STATUSES: ClassVar[tuple[str, ...]] = ("To Do", "In Progress", "Completed")

    task_id: str
    title: str
    course: str
    due_date: str = ""
    priority: int = 3
    status: str = "To Do"
    subtasks: list[str] = field(default_factory=list)

    @staticmethod
    def _check(name: str, value: Any) -> None:
        if name in ("task_id", "title", "course"):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        elif name == "due_date":
            if not isinstance(value, str):
                raise ValueError("due_date must be a YYYY-MM-DD string or empty")
            if value:
                try:
                    parsed = date.fromisoformat(value)
                except ValueError:
                    raise ValueError("due_date must be a valid YYYY-MM-DD date") from None
                if parsed.isoformat() != value:
                    raise ValueError("due_date must use YYYY-MM-DD format")
        elif name == "priority":
            if type(value) is not int or not 1 <= value <= 4:
                raise ValueError("priority must be an integer from 1 to 4")
        elif name == "status":
            if not isinstance(value, str) or value not in Task.STATUSES:
                raise ValueError("status must be To Do, In Progress, or Completed")
        elif name == "subtasks":
            if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                raise ValueError("subtasks must be a list of strings")

    def __setattr__(self, name: str, value: Any) -> None:
        self._check(name, value)
        if name == "subtasks":
            value = list(value)
        object.__setattr__(self, name, value)

    def validate(self) -> None:
        """Check all fields, including any in-place edits to subtasks."""
        for item in fields(self):
            self._check(item.name, getattr(self, item.name))

    def to_dict(self) -> dict[str, Any]:
        """Return the seven protocol fields as JSON-compatible values."""
        self.validate()
        result = {item.name: getattr(self, item.name) for item in fields(self)}
        result["subtasks"] = list(self.subtasks)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Restore a task; omitted optional fields use constructor defaults."""
        if not isinstance(data, dict):
            raise ValueError("Task data must be a dictionary")
        allowed = {item.name for item in fields(cls)}
        if set(data) - allowed:
            raise ValueError("Task data contains unknown fields")
        if not {"task_id", "title", "course"} <= set(data):
            raise ValueError("Task data requires task_id, title, and course")
        return cls(**data)

    def to_json(self, *, indent: int | None = None) -> str:
        """Serialize with readable Unicode; does not write any files."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, text: str) -> Task:
        """Restore from a JSON object, applying the same field validation."""
        if not isinstance(text, str):
            raise ValueError("JSON input must be a string")
        return cls.from_dict(json.loads(text))
