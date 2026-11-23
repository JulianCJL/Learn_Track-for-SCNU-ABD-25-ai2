"""Unit tests for task.Task — the task entity / validation layer.

Scope: backend business logic only (no CLI, no storage, no file I/O).
Runner: python -m unittest discover -s tests -v   (standard library only)

Conventions used by the tests:
  * A task ID is supplied by TaskManager, so tests build tasks directly.
  * "today" is taken from datetime.date.today() so the suite never rots.
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from task import Task  # noqa: E402  (import after sys.path fix)


def make_task(**overrides: object) -> Task:
    """Build a valid task, letting a test override any single field."""
    data: dict[str, object] = {
        "task_id": "T-001",
        "title": "Write the SE proposal",
        "course": "Software Engineering",
    }
    data.update(overrides)
    return Task(**data)  # type: ignore[arg-type]


class TestTaskDefaults(unittest.TestCase):
    """Constructor defaults (TC-T-01 ... TC-T-03)."""

    def test_minimal_arguments_get_documented_defaults(self) -> None:
        task = make_task()
        self.assertEqual(task.due_date, "")
        self.assertEqual(task.priority, 3)
        self.assertEqual(task.status, "To Do")
        self.assertEqual(task.subtasks, [])

    def test_all_fields_can_be_given_explicitly(self) -> None:
        task = make_task(
            due_date="2026-11-20", priority=1, status="In Progress",
            subtasks=["Draft", "Proofread"],
        )
        self.assertEqual(task.task_id, "T-001")
        self.assertEqual(task.title, "Write the SE proposal")
        self.assertEqual(task.course, "Software Engineering")
        self.assertEqual(task.due_date, "2026-11-20")
        self.assertEqual(task.priority, 1)
        self.assertEqual(task.status, "In Progress")
        self.assertEqual(task.subtasks, ["Draft", "Proofread"])

    def test_status_vocabulary_is_exposed_and_stable(self) -> None:
        self.assertEqual(Task.STATUSES, ("To Do", "In Progress", "Completed"))


class TestTaskRequiredFields(unittest.TestCase):
    """task_id / title / course must be non-empty strings (TC-T-04 ... TC-T-08)."""

    FIELDS = ("task_id", "title", "course")

    def test_blank_and_whitespace_values_are_rejected(self) -> None:
        for name in self.FIELDS:
            for bad in ("", "   ", "\t\n"):
                with self.subTest(field=name, value=repr(bad)):
                    with self.assertRaises(ValueError):
                        make_task(**{name: bad})

    def test_non_string_values_are_rejected(self) -> None:
        for name in self.FIELDS:
            for bad in (None, 123, 4.5, ["a"], {"a": 1}):
                with self.subTest(field=name, value=repr(bad)):
                    with self.assertRaises(ValueError):
                        make_task(**{name: bad})

    def test_single_character_values_are_accepted(self) -> None:
        task = make_task(task_id="x", title="y", course="z")
        self.assertEqual((task.task_id, task.title, task.course), ("x", "y", "z"))

    def test_inner_whitespace_is_preserved(self) -> None:
        task = make_task(title="Read chapter 4  and  5")
        self.assertEqual(task.title, "Read chapter 4  and  5")


class TestTaskDueDate(unittest.TestCase):
    """due_date is YYYY-MM-DD or the empty string (TC-T-09 ... TC-T-14)."""

    def test_empty_string_means_no_deadline(self) -> None:
        self.assertEqual(make_task(due_date="").due_date, "")

    def test_valid_iso_dates_are_accepted(self) -> None:
        for value in ("2026-11-20", "2026-01-01", "2024-02-29", "2099-12-31"):
            with self.subTest(value=value):
                self.assertEqual(make_task(due_date=value).due_date, value)

    def test_impossible_calendar_dates_are_rejected(self) -> None:
        for value in ("2026-02-30", "2026-13-01", "2026-00-10", "2025-02-29"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    make_task(due_date=value)

    def test_non_iso_formats_are_rejected(self) -> None:
        for value in ("20/11/2026", "2026-11-20 10:00", "20261120", "2026-1-5",
                      " 2026-11-20", "2026-11-20\n", "November 20 2026", "26-11-20"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    make_task(due_date=value)

    def test_non_string_values_are_rejected(self) -> None:
        for bad in (None, 20261120, date(2026, 11, 20)):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    make_task(due_date=bad)

    def test_error_message_names_the_field(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            make_task(due_date="20/11/2026")
        self.assertIn("due_date", str(ctx.exception))


class TestTaskPriority(unittest.TestCase):
    """priority is an int in 1..4, 1 being highest (TC-T-15 ... TC-T-18)."""

    def test_all_four_levels_are_accepted(self) -> None:
        for value in (1, 2, 3, 4):
            with self.subTest(value=value):
                self.assertEqual(make_task(priority=value).priority, value)

    def test_out_of_range_values_are_rejected(self) -> None:
        for value in (0, 5, -1, 99):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    make_task(priority=value)

    def test_non_integer_values_are_rejected(self) -> None:
        for bad in ("1", 2.0, True, None, [1]):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    make_task(priority=bad)

    def test_failed_assignment_keeps_the_previous_value(self) -> None:
        task = make_task(priority=2)
        with self.assertRaises(ValueError):
            task.priority = 5
        self.assertEqual(task.priority, 2)


class TestTaskStatus(unittest.TestCase):
    """status must be one of the three documented values (TC-T-19 ... TC-T-21)."""

    def test_documented_values_are_accepted(self) -> None:
        for value in Task.STATUSES:
            with self.subTest(value=value):
                self.assertEqual(make_task(status=value).status, value)

    def test_unknown_or_miscased_values_are_rejected(self) -> None:
        for bad in ("todo", "Done", "To do", "IN PROGRESS", "Completed ", ""):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    make_task(status=bad)

    def test_non_string_values_are_rejected(self) -> None:
        for bad in (None, 1, ["To Do"]):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    make_task(status=bad)


class TestTaskSubtasks(unittest.TestCase):
    """subtasks is a list of strings, copied on assignment (TC-T-22 ... TC-T-28)."""

    def test_empty_and_normal_lists_are_accepted(self) -> None:
        self.assertEqual(make_task(subtasks=[]).subtasks, [])
        self.assertEqual(make_task(subtasks=["a"]).subtasks, ["a"])
        self.assertEqual(make_task(subtasks=["a", "b", "c"]).subtasks, ["a", "b", "c"])

    def test_blank_strings_are_stored_verbatim(self) -> None:
        # The entity does not trim; the CLI is responsible for filtering blanks.
        self.assertEqual(make_task(subtasks=[""]).subtasks, [""])

    def test_non_list_containers_are_rejected(self) -> None:
        for bad in ("Draft,Proofread", ("Draft",), {"Draft"}, None):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    make_task(subtasks=bad)

    def test_mixed_element_types_are_rejected(self) -> None:
        for bad in ([1], ["ok", 2], [None], [["nested"]]):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    make_task(subtasks=bad)

    def test_assignment_copies_the_list_so_callers_cannot_share_state(self) -> None:
        source = ["Draft"]
        task = make_task(subtasks=source)
        source.append("Leaked")
        self.assertEqual(task.subtasks, ["Draft"])
        task.subtasks.append("OnlyHere")
        self.assertEqual(source, ["Draft", "Leaked"])

    def test_invalid_in_place_edit_is_caught_by_validate(self) -> None:
        task = make_task(subtasks=["Draft"])
        task.subtasks.append(123)  # bypasses __setattr__ on purpose
        with self.assertRaises(ValueError):
            task.validate()
        with self.assertRaises(ValueError):
            task.to_dict()

    def test_in_place_edit_can_be_repaired_by_reassignment(self) -> None:
        task = make_task(subtasks=["Draft"])
        task.subtasks.append(123)
        task.subtasks = [item for item in task.subtasks if isinstance(item, str)]
        task.validate()
        self.assertEqual(task.to_dict()["subtasks"], ["Draft"])


class TestTaskProtocolMapping(unittest.TestCase):
    """to_dict / from_dict / to_json / from_json round trips (TC-T-29 ... TC-T-36)."""

    PROTOCOL_KEYS = {"task_id", "title", "course", "due_date",
                     "priority", "status", "subtasks"}

    def test_to_dict_returns_exactly_the_seven_protocol_fields(self) -> None:
        record = make_task(subtasks=["a"]).to_dict()
        self.assertEqual(set(record), self.PROTOCOL_KEYS)
        self.assertEqual(len(record), 7)
        self.assertEqual(record["subtasks"], ["a"])

    def test_to_dict_does_not_expose_the_internal_list(self) -> None:
        task = make_task(subtasks=["a"])
        record = task.to_dict()
        record["subtasks"].append("b")
        self.assertEqual(task.subtasks, ["a"])

    def test_to_dict_values_are_json_compatible(self) -> None:
        record = make_task(due_date="2026-11-20", priority=1).to_dict()
        json.dumps(record)  # must not raise
        self.assertIsInstance(record["priority"], int)
        self.assertIsInstance(record["subtasks"], list)

    def test_from_dict_round_trip_is_lossless(self) -> None:
        original = make_task(due_date="2026-11-20", priority=1,
                             status="In Progress", subtasks=["Draft", "Proofread"])
        restored = Task.from_dict(original.to_dict())
        self.assertEqual(restored.to_dict(), original.to_dict())
        self.assertEqual(restored, original)

    def test_from_dict_applies_constructor_defaults_to_omitted_fields(self) -> None:
        restored = Task.from_dict(
            {"task_id": "T-9", "title": "Read notes", "course": "AI"})
        self.assertEqual(restored.due_date, "")
        self.assertEqual(restored.priority, 3)
        self.assertEqual(restored.status, "To Do")
        self.assertEqual(restored.subtasks, [])

    def test_from_dict_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValueError):
            Task.from_dict({"task_id": "T-1", "title": "t", "course": "c",
                            "difficulty": 2})

    def test_from_dict_requires_the_three_mandatory_fields(self) -> None:
        for missing in ("task_id", "title", "course"):
            payload = {"task_id": "T-1", "title": "t", "course": "c"}
            del payload[missing]
            with self.subTest(missing=missing):
                with self.assertRaises(ValueError):
                    Task.from_dict(payload)

    def test_from_dict_rejects_non_dictionaries(self) -> None:
        for bad in ([], "text", 1, None, ("task_id", "title", "course")):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    Task.from_dict(bad)  # type: ignore[arg-type]

    def test_from_dict_still_validates_values(self) -> None:
        for field, bad in (("priority", 9), ("status", "Done"),
                           ("due_date", "2026-02-30"), ("subtasks", "x")):
            payload = {"task_id": "T-1", "title": "t", "course": "c", field: bad}
            with self.subTest(field=field, value=repr(bad)):
                with self.assertRaises(ValueError):
                    Task.from_dict(payload)


class TestTaskJson(unittest.TestCase):
    """JSON helpers: Unicode friendly, no file I/O, validation preserved."""

    def test_to_json_keeps_non_ascii_readable(self) -> None:
        text = make_task(title="复习第四章", course="数据结构").to_json()
        self.assertIn("复习第四章", text)
        self.assertNotIn("\\u", text)

    def test_to_json_indent_is_optional(self) -> None:
        compact = make_task().to_json()
        pretty = make_task().to_json(indent=2)
        self.assertNotIn("\n", compact)
        self.assertIn("\n  ", pretty)

    def test_from_json_round_trip(self) -> None:
        original = make_task(task_id="T-7", title="Midterm revision", course="AI",
                             due_date="2026-11-25", priority=2,
                             status="In Progress", subtasks=["Ch1", "Ch2"])
        restored = Task.from_json(original.to_json())
        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_from_json_rejects_malformed_text(self) -> None:
        for bad in ("{ not json", "", "[1, 2]"):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    Task.from_json(bad)

    def test_from_json_rejects_non_string_input(self) -> None:
        for bad in (None, 1, b"{}"):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    Task.from_json(bad)  # type: ignore[arg-type]


class TestTaskValidate(unittest.TestCase):
    """validate() re-checks every field of an existing instance."""

    def test_validate_passes_for_a_well_formed_task(self) -> None:
        make_task(due_date="2026-11-20", priority=1,
                  status="Completed", subtasks=["a"]).validate()

    def test_validate_detects_a_corrupted_field(self) -> None:
        task = make_task()
        object.__setattr__(task, "priority", 7)  # deliberate bypass
        with self.assertRaises(ValueError):
            task.validate()


if __name__ == "__main__":
    unittest.main(verbosity=2)
