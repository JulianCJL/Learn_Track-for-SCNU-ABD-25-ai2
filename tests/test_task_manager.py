"""Unit tests for task_manager.TaskManager — the business layer.

Scope: CRUD, sorting, filtering, statistics and snapshot isolation. No CLI,
no file I/O (the storage layer has its own test module).

Runner: python -m unittest discover -s tests -v
"""

from __future__ import annotations

import re
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from task import Task  # noqa: E402
from task_manager import TaskManager  # noqa: E402


def task(task_id: str, *, title: str = "Task", course: str = "SE",
         due_date: str = "", priority: int = 3,
         status: str = "To Do", subtasks: list[str] | None = None) -> Task:
    return Task(task_id, title, course, due_date, priority, status,
                [] if subtasks is None else subtasks)


def day(offset: int) -> str:
    """ISO date relative to today, so overdue tests never expire."""
    return (date.today() + timedelta(days=offset)).isoformat()


class TestInitialisation(unittest.TestCase):
    """TC-M-01 ... TC-M-04."""

    def test_empty_by_default(self) -> None:
        manager = TaskManager()
        self.assertEqual(manager.get_tasks(), [])
        self.assertEqual(manager.statistics()["total"], 0)

    def test_none_is_treated_as_empty(self) -> None:
        self.assertEqual(TaskManager(None).get_tasks(), [])

    def test_restores_supplied_tasks_and_keeps_their_ids(self) -> None:
        tasks = [task("aaa"), task("bbb", due_date="2026-11-20")]
        manager = TaskManager(tasks)
        self.assertEqual({t.task_id for t in manager.get_tasks()}, {"aaa", "bbb"})
        self.assertEqual(manager.get_task("aaa").task_id, "aaa")

    def test_restored_tasks_are_snapshots_not_the_same_objects(self) -> None:
        original = task("aaa", subtasks=["Draft"])
        manager = TaskManager([original])
        original.subtasks = ["Changed outside"]
        self.assertEqual(manager.get_task("aaa").subtasks, ["Draft"])

    def test_duplicate_ids_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TaskManager([task("dup"), task("dup")])

    def test_non_task_entries_are_rejected(self) -> None:
        for bad in (["not a task"], [None], [{"task_id": "aaa"}]):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    TaskManager(bad)  # type: ignore[arg-type]

    def test_instances_do_not_share_state(self) -> None:
        first, second = TaskManager(), TaskManager()
        first.add_task("Only in first", "SE")
        self.assertEqual(second.get_tasks(), [])


class TestAddTask(unittest.TestCase):
    """TC-M-05 ... TC-M-10."""

    def test_returns_the_new_task_and_stores_it(self) -> None:
        manager = TaskManager()
        created = manager.add_task("Finish proposal", "SE", "2026-11-20", 1,
                                   ["Draft", "Proofread"])
        self.assertEqual(created.title, "Finish proposal")
        self.assertEqual(created.status, "To Do")
        self.assertEqual(manager.get_task(created.task_id).to_dict(), created.to_dict())
        self.assertEqual(manager.statistics()["total"], 1)

    def test_id_is_a_32_char_hex_string(self) -> None:
        created = TaskManager().add_task("t", "c")
        self.assertRegex(created.task_id, r"^[0-9a-f]{32}$")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{32}", created.task_id))

    def test_ids_are_unique_even_for_identical_titles(self) -> None:
        manager = TaskManager()
        ids = {manager.add_task("Same title", "SE").task_id for _ in range(5)}
        self.assertEqual(len(ids), 5)
        self.assertEqual(manager.statistics()["total"], 5)

    def test_defaults_match_the_documented_contract(self) -> None:
        created = TaskManager().add_task("t", "c")
        self.assertEqual(created.due_date, "")
        self.assertEqual(created.priority, 3)
        self.assertEqual(created.status, "To Do")
        self.assertEqual(created.subtasks, [])

    def test_subtask_list_is_copied_on_the_way_in(self) -> None:
        manager = TaskManager()
        given = ["Draft"]
        created = manager.add_task("t", "c", subtasks=given)
        given.append("Added later")
        self.assertEqual(manager.get_task(created.task_id).subtasks, ["Draft"])

    def test_invalid_input_is_rejected_before_any_state_changes(self) -> None:
        cases = (
            ("", "SE", "", 3),              # empty title
            ("t", "  ", "", 3),             # blank course
            ("t", "SE", "2026-02-30", 3),   # impossible date
            ("t", "SE", "", 9),             # priority out of range
        )
        for title, course, due, priority in cases:
            with self.subTest(title=title, course=course, due=due, priority=priority):
                manager = TaskManager()
                with self.assertRaises(ValueError):
                    manager.add_task(title, course, due, priority)
                self.assertEqual(manager.get_tasks(), [])

    def test_returned_task_is_a_snapshot(self) -> None:
        manager = TaskManager()
        created = manager.add_task("t", "c", subtasks=["a"])
        created.subtasks.append(123)  # breaks the snapshot only
        self.assertEqual(manager.get_task(created.task_id).subtasks, ["a"])


class TestGetTask(unittest.TestCase):
    """TC-M-11 ... TC-M-14."""

    def test_returns_a_copy_so_callers_cannot_corrupt_the_store(self) -> None:
        manager = TaskManager()
        created = manager.add_task("t", "c", subtasks=["a"])
        fetched = manager.get_task(created.task_id)
        self.assertIsNot(fetched, manager.get_task(created.task_id))
        fetched.title = "Locally renamed"
        fetched.subtasks = ["Locally changed"]
        stored = manager.get_task(created.task_id)
        self.assertEqual(stored.title, "t")
        self.assertEqual(stored.subtasks, ["a"])

    def test_unknown_id_raises_with_the_id_in_the_message(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            TaskManager().get_task("missing-id")
        self.assertIn("missing-id", str(ctx.exception))

    def test_blank_and_non_string_ids_are_rejected(self) -> None:
        manager = TaskManager()
        manager.add_task("t", "c")
        for bad in ("", "   ", None, 1, ["id"]):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    manager.get_task(bad)  # type: ignore[arg-type]


class TestGetTasksOrdering(unittest.TestCase):
    """Sorting contract: deadline asc, undated last, then priority, then id."""

    def setUp(self) -> None:
        self.manager = TaskManager([
            task("aaa", due_date="2026-11-20", priority=2),
            task("bbb", due_date="", priority=1),
            task("ccc", due_date="2026-11-18", priority=4),
            task("ddd", due_date="2026-11-20", priority=1),
            task("eee", due_date="2026-11-20", priority=2),
        ])

    def test_expected_total_order(self) -> None:
        order = [t.task_id for t in self.manager.get_tasks()]
        self.assertEqual(order, ["ccc", "ddd", "aaa", "eee", "bbb"])

    def test_undated_tasks_always_come_last(self) -> None:
        self.assertEqual(self.manager.get_tasks()[-1].task_id, "bbb")

    def test_equal_deadline_and_priority_falls_back_to_id(self) -> None:
        ids = [t.task_id for t in self.manager.get_tasks()]
        self.assertLess(ids.index("aaa"), ids.index("eee"))

    def test_returns_every_task_exactly_once(self) -> None:
        tasks = self.manager.get_tasks()
        self.assertEqual(len(tasks), 5)
        self.assertEqual(len({t.task_id for t in tasks}), 5)

    def test_each_call_returns_fresh_copies(self) -> None:
        first = self.manager.get_tasks()
        second = self.manager.get_tasks()
        self.assertEqual([t.task_id for t in first], [t.task_id for t in second])
        for a, b in zip(first, second):
            self.assertIsNot(a, b)


class TestUpdateTask(unittest.TestCase):
    """TC-M-20 ... TC-M-28."""

    def setUp(self) -> None:
        self.manager = TaskManager()
        self.created = self.manager.add_task("Old title", "SE", "", 3, ["a"])

    def test_each_supported_field_can_be_updated(self) -> None:
        cases = (
            ("title", "New title"), ("course", "AI"),
            ("due_date", "2026-12-01"), ("priority", 1),
            ("status", "Completed"), ("subtasks", ["x", "y"]),
        )
        for field, value in cases:
            with self.subTest(field=field):
                updated = self.manager.update_task(self.created.task_id, **{field: value})
                self.assertEqual(getattr(updated, field), value)
                self.assertEqual(getattr(self.manager.get_task(self.created.task_id), field),
                                 value)

    def test_untouched_fields_survive_an_update(self) -> None:
        self.manager.update_task(self.created.task_id, title="Changed")
        stored = self.manager.get_task(self.created.task_id)
        self.assertEqual(stored.course, "SE")
        self.assertEqual(stored.priority, 3)
        self.assertEqual(stored.subtasks, ["a"])

    def test_unknown_field_is_rejected_and_state_is_unchanged(self) -> None:
        before = self.manager.get_task(self.created.task_id).to_dict()
        with self.assertRaises(ValueError):
            self.manager.update_task(self.created.task_id, difficulty=5)
        self.assertEqual(self.manager.get_task(self.created.task_id).to_dict(), before)

    def test_task_id_cannot_be_changed(self) -> None:
        # task_id is the parameter name itself, so Python rejects the duplicate
        # binding before the method body runs; either way the ID stays put.
        with self.assertRaises(TypeError):
            self.manager.update_task(self.created.task_id, **{"task_id": "hacked"})
        self.assertEqual(self.manager.get_task(self.created.task_id).task_id,
                         self.created.task_id)
        with self.assertRaises(ValueError):
            self.manager.update_task(self.created.task_id, **{"unexpected": 1})

    def test_invalid_value_is_rejected_and_state_is_unchanged(self) -> None:
        before = self.manager.get_task(self.created.task_id).to_dict()
        for field, bad in (("priority", 0), ("status", "Done"),
                           ("due_date", "2026-02-30"), ("title", ""),
                           ("subtasks", "a,b")):
            with self.subTest(field=field, value=repr(bad)):
                with self.assertRaises(ValueError):
                    self.manager.update_task(self.created.task_id, **{field: bad})
                self.assertEqual(self.manager.get_task(self.created.task_id).to_dict(),
                                 before)

    def test_missing_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.manager.update_task("nope", title="x")

    def test_empty_update_is_a_no_op(self) -> None:
        before = self.manager.get_task(self.created.task_id).to_dict()
        self.manager.update_task(self.created.task_id)
        self.assertEqual(self.manager.get_task(self.created.task_id).to_dict(), before)

    def test_due_date_can_be_cleared(self) -> None:
        self.manager.update_task(self.created.task_id, due_date="2026-12-01")
        self.manager.update_task(self.created.task_id, due_date="")
        self.assertEqual(self.manager.get_task(self.created.task_id).due_date, "")

    def test_returned_task_is_a_snapshot(self) -> None:
        updated = self.manager.update_task(self.created.task_id, title="New")
        updated.title = "Mutated afterwards"
        self.assertEqual(self.manager.get_task(self.created.task_id).title, "New")


class TestDeleteTask(unittest.TestCase):
    """TC-M-29 ... TC-M-31."""

    def test_delete_removes_the_task_and_returns_its_snapshot(self) -> None:
        manager = TaskManager()
        created = manager.add_task("t", "c", subtasks=["a"])
        deleted = manager.delete_task(created.task_id)
        self.assertEqual(deleted.to_dict(), created.to_dict())
        self.assertEqual(manager.get_tasks(), [])
        with self.assertRaises(ValueError):
            manager.get_task(created.task_id)

    def test_deleting_twice_raises(self) -> None:
        manager = TaskManager()
        created = manager.add_task("t", "c")
        manager.delete_task(created.task_id)
        with self.assertRaises(ValueError):
            manager.delete_task(created.task_id)

    def test_deleting_an_unknown_id_raises_and_keeps_other_tasks(self) -> None:
        manager = TaskManager([task("keep")])
        with self.assertRaises(ValueError):
            manager.delete_task("missing")
        self.assertEqual([t.task_id for t in manager.get_tasks()], ["keep"])


class TestFilterTasks(unittest.TestCase):
    """Exact-match course/status filters, ANDed, plus overdue (TC-M-32 ... TC-M-40)."""

    def setUp(self) -> None:
        self.manager = TaskManager([
            task("a1", title="Past due open", course="SE", due_date=day(-3)),
            task("a2", title="Past due done", course="SE", due_date=day(-3),
                 status="Completed"),
            task("a3", title="Due today", course="AI", due_date=day(0)),
            task("a4", title="Future", course="AI", due_date=day(10)),
            task("a5", title="No date", course="Math", priority=1),
        ])

    def ids(self, **kwargs: object) -> list[str]:
        return [t.task_id for t in self.manager.filter_tasks(**kwargs)]  # type: ignore[arg-type]

    def test_no_arguments_returns_everything_in_sort_order(self) -> None:
        self.assertEqual(self.ids(), [t.task_id for t in self.manager.get_tasks()])
        self.assertEqual(len(self.ids()), 5)

    def test_course_filter_is_an_exact_match(self) -> None:
        self.assertEqual(self.ids(course="SE"), ["a1", "a2"])
        self.assertEqual(self.ids(course="AI"), ["a3", "a4"])
        self.assertEqual(self.ids(course="Math"), ["a5"])
        self.assertEqual(self.ids(course="Unknown"), [])

    def test_course_filter_is_case_sensitive(self) -> None:
        self.assertEqual(self.ids(course="se"), [])

    def test_status_filter(self) -> None:
        self.assertEqual(self.ids(status="Completed"), ["a2"])
        self.assertEqual(self.ids(status="To Do"), ["a1", "a3", "a4", "a5"])
        self.assertEqual(self.ids(status="In Progress"), [])

    def test_overdue_excludes_completed_and_undated_and_today(self) -> None:
        self.assertEqual(self.ids(overdue_only=True), ["a1"])

    def test_overdue_includes_in_progress_tasks(self) -> None:
        self.manager.update_task("a3", due_date=day(-1), status="In Progress")
        self.assertIn("a3", self.ids(overdue_only=True))

    def test_filters_combine_with_and(self) -> None:
        self.assertEqual(self.ids(course="SE", status="Completed"), ["a2"])
        self.assertEqual(self.ids(course="AI", overdue_only=True), [])
        self.assertEqual(self.ids(course="SE", status="To Do", overdue_only=True), ["a1"])
        self.assertEqual(self.ids(status="Completed", overdue_only=True), [])

    def test_results_are_snapshots(self) -> None:
        result = self.manager.filter_tasks(course="SE")
        result[0].status = "Completed"
        self.assertEqual(self.manager.get_task("a1").status, "To Do")

    def test_invalid_arguments_are_rejected(self) -> None:
        for kwargs in ({"status": "Done"}, {"status": ""}, {"course": ""},
                       {"course": "   "}, {"overdue_only": 1},
                       {"overdue_only": "yes"}):
            with self.subTest(**{k: repr(v) for k, v in kwargs.items()}):
                with self.assertRaises(ValueError):
                    self.manager.filter_tasks(**kwargs)  # type: ignore[arg-type]


class TestStatistics(unittest.TestCase):
    """TC-M-41 ... TC-M-45."""

    KEYS = {"total", "to_do", "in_progress", "completed", "overdue", "completion_rate"}

    def test_empty_manager_reports_zeroes(self) -> None:
        stats = TaskManager().statistics()
        self.assertEqual(set(stats), self.KEYS)
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["overdue"], 0)
        self.assertEqual(stats["completion_rate"], 0.0)

    def test_counts_by_status_and_overdue(self) -> None:
        manager = TaskManager([
            task("a1", due_date=day(-2)),                      # overdue To Do
            task("a2", due_date=day(-2), status="Completed"),  # past due, done
            task("a3", status="In Progress"),
            task("a4", status="Completed"),
            task("a5", due_date=day(5)),
        ])
        stats = manager.statistics()
        self.assertEqual(stats["total"], 5)
        self.assertEqual(stats["to_do"], 2)
        self.assertEqual(stats["in_progress"], 1)
        self.assertEqual(stats["completed"], 2)
        self.assertEqual(stats["overdue"], 1)
        self.assertEqual(stats["completion_rate"], 40.0)

    def test_completion_rate_is_rounded_to_two_decimals(self) -> None:
        manager = TaskManager([task("a1"), task("a2"), task("a3", status="Completed")])
        self.assertEqual(manager.statistics()["completion_rate"], 33.33)

    def test_completion_rate_is_100_when_all_done(self) -> None:
        manager = TaskManager([task("a1", status="Completed")])
        self.assertEqual(manager.statistics()["completion_rate"], 100.0)

    def test_statistics_reflect_changes_immediately(self) -> None:
        manager = TaskManager()
        created = manager.add_task("t", "c")
        manager.update_task(created.task_id, status="Completed")
        self.assertEqual(manager.statistics()["completed"], 1)
        manager.delete_task(created.task_id)
        self.assertEqual(manager.statistics()["total"], 0)

    def test_overdue_boundary_is_strictly_before_today(self) -> None:
        manager = TaskManager([task("a1", due_date=day(0)), task("a2", due_date=day(-1))])
        self.assertEqual(manager.statistics()["overdue"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
