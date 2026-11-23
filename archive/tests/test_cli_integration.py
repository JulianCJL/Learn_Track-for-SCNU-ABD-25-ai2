"""Integration tests for the LearnTrack CLI — whole menus, real input paths.

Two layers are exercised here:
  1. In-process: learntrack_cli.run_cli(manager) driven by scripted keyboard
     input, covering every menu option, normal / illegal / boundary input.
  2. Out-of-process: the real entry point (python learntrack_cli.py) started in
     a temporary working directory, proving storage + CLI + restart behaviour.

The project's own tasks.json is never touched: every test runs in its own
temporary directory.

Tests marked @unittest.expectedFailure reproduce defects that exist in the
current source. They are reported in BUG_LIST.md and intentionally NOT fixed
by this test task (see the bug list for the reasoning).
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unicodedata import east_asian_width
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from json_storage_fixed import create_manager  # noqa: E402
from learntrack_cli import run_cli  # noqa: E402


def day(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


class ScriptedInput:
    """Feeds answers one by one; a callable answer is evaluated at prompt time."""

    def __init__(self, answers: list[object]) -> None:
        self.queue = list(answers)
        self.prompts: list[str] = []
        self.consumed = 0

    def __call__(self, prompt: str = "") -> str:
        self.prompts.append(prompt)
        if self.consumed >= len(self.queue):
            raise EOFError
        item = self.queue[self.consumed]
        self.consumed += 1
        return item(prompt) if callable(item) else str(item)  # type: ignore[return-value]


class CliTestCase(unittest.TestCase):
    """Base class: temp cwd-less manager plus a session driver."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.path = self.dir / "tasks.json"
        self.manager = create_manager(self.path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def session(self, answers: list[object]) -> tuple[str, ScriptedInput]:
        feed = ScriptedInput(answers)
        out = io.StringIO()
        with mock.patch("builtins.input", new=feed), contextlib.redirect_stdout(out):
            run_cli(self.manager)
        return out.getvalue(), feed

    # helpers ----------------------------------------------------------
    def add(self, title: str, course: str, due: str = "", priority: str = "3",
            subtasks: str = "") -> list[object]:
        return ["1", title, course, due, priority, subtasks]

    def stored_records(self) -> list[dict]:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []

    def first_id(self) -> str:
        return self.manager.get_tasks()[0].task_id


class TestAddAndList(CliTestCase):
    """Menu 1 and 2: create and display tasks (TC-I-01 ... TC-I-06)."""

    def test_add_task_prints_id_and_persists_all_fields(self) -> None:
        output, _ = self.session(self.add("Finish proposal", "Software Engineering",
                                         "2026-12-10", "1", "Draft,Proofread") + ["0"])
        created = self.manager.get_task(self.first_id())
        self.assertIn(f"Added task {created.task_id}: Finish proposal", output)
        self.assertEqual(created.course, "Software Engineering")
        self.assertEqual(created.due_date, "2026-12-10")
        self.assertEqual(created.priority, 1)
        self.assertEqual(created.subtasks, ["Draft", "Proofread"])
        self.assertEqual(len(self.stored_records()), 1)
        self.assertIn("Goodbye.", output)

    def test_list_shows_header_and_one_row_per_task(self) -> None:
        output, _ = self.session(
            self.add("A task", "SE", "2026-12-10", "2")
            + self.add("Second task", "AI")
            + ["2", "0"])
        header = next(line for line in output.splitlines() if line.startswith("ID"))
        for column in ("ID", "Due date", "P", "Status", "Course", "Title"):
            self.assertIn(column, header)
        self.assertIn("A task", output)
        self.assertIn("Second task", output)
        self.assertIn("No date", output)  # blank due date is displayed friendly
        self.assertEqual(self.manager.statistics()["total"], 2)

    def test_list_is_empty_message_when_store_is_empty(self) -> None:
        output, _ = self.session(["2", "0"])
        self.assertIn("No tasks to show.", output)

    def test_list_order_is_deadline_then_priority(self) -> None:
        output, _ = self.session(
            self.add("Late", "SE", "2026-12-31", "1")
            + self.add("Early", "SE", "2026-11-21", "4")
            + self.add("Undated", "SE", "", "1")
            + ["2", "0"])
        rows = [line for line in output.splitlines() if line.strip().startswith(tuple("0123456789abcdef"))]
        listing = "\n".join(rows)
        self.assertLess(listing.index("Early"), listing.index("Late"))
        self.assertLess(listing.index("Late"), listing.index("Undated"))

    def test_duplicate_titles_are_allowed(self) -> None:
        output, _ = self.session(self.add("Same", "SE") + self.add("Same", "SE") + ["0"])
        self.assertEqual(self.manager.statistics()["total"], 2)
        self.assertEqual(output.count("Added task"), 2)

    def test_unicode_input_round_trips_through_the_cli_and_the_file(self) -> None:
        self.session(self.add("复习第四章", "数据结构", "2026-12-10", "1", "读课本,做题") + ["0"])
        stored = self.manager.get_task(self.first_id())
        self.assertEqual(stored.title, "复习第四章")
        self.assertEqual(stored.subtasks, ["读课本", "做题"])
        self.assertEqual(self.stored_records()[0]["title"], "复习第四章")


class TestViewAndLongListBoundaries(CliTestCase):
    """Menu 3 plus display boundaries (TC-I-07 ... TC-I-10)."""

    def test_view_prints_every_field_and_numbered_subtasks(self) -> None:
        self.session(self.add("Finish proposal", "SE", "2026-12-10", "1", "Draft,Proofread"))
        output, _ = self.session(["3", self.first_id(), "0"])
        self.assertIn(f"ID: {self.first_id()}", output)
        self.assertIn("Title: Finish proposal", output)
        self.assertIn("Course: SE", output)
        self.assertIn("Due date: 2026-12-10", output)
        self.assertIn("Priority: 1", output)
        self.assertIn("Status: To Do", output)
        self.assertIn("  1. Draft", output)
        self.assertIn("  2. Proofread", output)

    def test_view_without_subtasks_says_none(self) -> None:
        self.session(self.add("No steps", "SE"))
        output, _ = self.session(["3", self.first_id(), "0"])
        self.assertIn("Subtasks:", output)
        self.assertIn("  None", output)

    def test_view_without_deadline_says_not_set(self) -> None:
        self.session(self.add("No deadline", "SE"))
        output, _ = self.session(["3", self.first_id(), "0"])
        self.assertIn("Due date: Not set", output)

    def test_long_course_name_does_not_break_the_table(self) -> None:
        long_course = "Introduction to Software Engineering and Team Project"
        self.session(self.add("Long course task", long_course))
        output, _ = self.session(["2", "0"])
        self.assertIn("Long course task", output)
        self.assertIn("Introduction to Software", output)


class TestUpdate(CliTestCase):
    """Menu 4: every editable field (TC-I-11 ... TC-I-16)."""

    def setUp(self) -> None:
        super().setUp()
        self.session(self.add("Original", "SE", "2026-12-10", "2", "Step"))

    def test_update_title(self) -> None:
        output, _ = self.session(["4", self.first_id(), "1", "Renamed", "0"])
        self.assertIn("Updating Original", output)
        self.assertIn(f"Updated task {self.first_id()}.", output)
        self.assertEqual(self.manager.get_task(self.first_id()).title, "Renamed")

    def test_update_course(self) -> None:
        self.session(["4", self.first_id(), "2", "Artificial Intelligence", "0"])
        self.assertEqual(self.manager.get_task(self.first_id()).course,
                         "Artificial Intelligence")

    def test_update_due_date_and_clear_it(self) -> None:
        self.session(["4", self.first_id(), "3", "2026-12-20", "0"])
        self.assertEqual(self.manager.get_task(self.first_id()).due_date, "2026-12-20")
        self.session(["4", self.first_id(), "3", "", "0"])
        self.assertEqual(self.manager.get_task(self.first_id()).due_date, "")

    def test_update_priority(self) -> None:
        self.session(["4", self.first_id(), "4", "4", "0"])
        self.assertEqual(self.manager.get_task(self.first_id()).priority, 4)

    def test_update_status_and_reflect_it_in_statistics(self) -> None:
        self.session(["4", self.first_id(), "5", "3", "7", "0"])
        self.assertEqual(self.manager.get_task(self.first_id()).status, "Completed")
        output, _ = self.session(["7", "0"])
        self.assertIn("Completed: 1", output)

    def test_update_subtasks_and_clear_them(self) -> None:
        self.session(["4", self.first_id(), "6", "A,B,C", "0"])
        self.assertEqual(self.manager.get_task(self.first_id()).subtasks, ["A", "B", "C"])
        self.session(["4", self.first_id(), "6", "", "0"])
        self.assertEqual(self.manager.get_task(self.first_id()).subtasks, [])

    def test_update_is_persisted_after_restart(self) -> None:
        self.session(["4", self.first_id(), "1", "Persisted rename", "0"])
        reopened = create_manager(self.path)
        self.assertEqual(reopened.get_task(self.first_id()).title, "Persisted rename")


class TestFilter(CliTestCase):
    """Menu 6: all three filters plus the empty-result path (TC-I-17 ... TC-I-21)."""

    def setUp(self) -> None:
        super().setUp()
        self.session(
            self.add("Past due open", "SE", day(-3), "2")
            + self.add("Past due done", "SE", day(-3), "2")
            + self.add("Due today", "AI", day(0), "1")
            + self.add("Future work", "AI", day(5), "3")
            + self.add("No deadline", "Math", "", "4")
            + ["4", lambda p: self._find("Past due done"), "5", "3", "0"])

    def _find(self, title: str) -> str:
        for task in self.manager.get_tasks():
            if task.title == title:
                return task.task_id
        raise AssertionError(f"missing task {title}")

    def test_filter_by_course(self) -> None:
        output, _ = self.session(["6", "1", "SE", "0"])
        self.assertIn("1. By course", output)
        self.assertIn("Past due open", output)
        self.assertIn("Past due done", output)
        self.assertNotIn("Future work", output)

    def test_filter_by_status(self) -> None:
        output, _ = self.session(["6", "2", "3", "0"])
        self.assertIn("Past due done", output)
        self.assertNotIn("Future work", output)

    def test_filter_overdue_skips_completed_and_today(self) -> None:
        output, _ = self.session(["6", "3", "0"])
        self.assertIn("Past due open", output)
        self.assertNotIn("Past due done", output)
        self.assertNotIn("Due today", output)

    def test_filter_with_no_match_reports_empty(self) -> None:
        output, _ = self.session(["6", "1", "Unknown Course", "0"])
        self.assertIn("No tasks to show.", output)

    def test_filter_by_ill_formed_status_choice_is_rejected(self) -> None:
        output, _ = self.session(["6", "2", "9", "2", "0"])
        self.assertIn("Choose 1, 2, or 3.", output)


class TestDelete(CliTestCase):
    """Menu 5: confirmation, cancel, boundary of the last task (TC-I-22 ... TC-I-24)."""

    def test_delete_with_confirmation_removes_the_task_everywhere(self) -> None:
        self.session(self.add("To delete", "SE"))
        output, feed = self.session(["5", self.first_id(), "y", "2", "0"])
        self.assertIn("Delete 'To delete'? (y/N): ", feed.prompts)
        self.assertIn("Task deleted.", output)
        self.assertIn("No tasks to show.", output)
        self.assertEqual(self.stored_records(), [])

    def test_delete_cancelled_by_anything_but_y(self) -> None:
        self.session(self.add("Keep me", "SE"))
        output, _ = self.session(["5", self.first_id(), "n", "0"])
        self.assertIn("Delete cancelled.", output)
        self.assertEqual(self.manager.statistics()["total"], 1)

        output, _ = self.session(["5", self.first_id(), "yes", "0"])
        self.assertIn("Delete cancelled.", output)
        self.assertEqual(self.manager.statistics()["total"], 1)

    def test_delete_last_task_leaves_a_clean_statistics_page(self) -> None:
        self.session(self.add("Only one", "SE"))
        output, _ = self.session(["5", self.first_id(), "Y", "7", "0"])
        self.assertIn("Total tasks: 0", output)
        self.assertIn("Completion rate: 0.0%", output)


class TestStatistics(CliTestCase):
    """Menu 7 (TC-I-25 ... TC-I-27)."""

    def test_statistics_page_lists_every_counter(self) -> None:
        output, _ = self.session(["7", "0"])
        for label in ("Task statistics", "Total tasks: 0", "To Do: 0",
                      "In Progress: 0", "Completed: 0", "Overdue: 0",
                      "Completion rate: 0.0%"):
            self.assertIn(label, output)

    def test_statistics_counts_mixed_tasks(self) -> None:
        self.session(
            self.add("A", "SE", day(-2), "2")
            + self.add("B", "SE", day(-2), "2")
            + ["4", lambda p: self._id_of("B"), "5", "3"]
            + self.add("C", "AI", day(5), "1")
            + ["7", "0"])
        output, _ = self.session(["7", "0"])
        self.assertIn("Total tasks: 3", output)
        self.assertIn("Completed: 1", output)
        self.assertIn("Overdue: 1", output)
        self.assertIn("Completion rate: 33.33%", output)

    def _id_of(self, title: str) -> str:
        for task in self.manager.get_tasks():
            if task.title == title:
                return task.task_id
        raise AssertionError(f"missing task {title}")


class TestMenuCoverage(CliTestCase):
    """One long session that walks every menu option (acceptance criterion)."""

    def test_every_menu_option_is_exercised_in_one_session(self) -> None:
        answers: list[object] = []
        answers += self.add("Finish SE proposal", "Software Engineering",
                            "2026-12-10", "1", "Draft,Proofread")
        answers += self.add("Revise AI midterm", "Artificial Intelligence", "", "2", "")
        answers += self.add("Read queue chapter", "Data Structures", day(-2), "3", "Ch2,Ch3")
        answers += self.add("Group meeting", "Software Engineering", day(0), "4", "")
        answers += ["2"]
        answers += ["3", lambda p: self.manager.get_tasks()[0].task_id]
        answers += ["4", lambda p: self.manager.get_tasks()[0].task_id, "5", "2"]
        answers += ["6", "1", "Software Engineering"]
        answers += ["6", "2", "3"]
        answers += ["6", "3"]
        answers += ["7"]
        answers += ["5", lambda p: self.manager.get_tasks()[-1].task_id, "y"]
        answers += ["0"]

        output, feed = self.session(answers)

        for marker in ("1. Add task", "2. List tasks", "3. View task details",
                       "4. Update task", "5. Delete task", "6. Filter tasks",
                       "7. View statistics", "0. Exit"):
            self.assertIn(marker, output)
        for marker in ("Added task", "Due date", "Title:", "Updating ",
                       "Updated task", "Task deleted.", "1. By course",
                       "Task statistics", "Goodbye."):
            self.assertIn(marker, output)

        # All eight answers were consumed, i.e. the walkthrough reached the exit.
        self.assertEqual(feed.consumed, len(answers))

        # Final state: four added, one deleted.
        self.assertEqual(self.manager.statistics()["total"], 3)
        titles = {t.title for t in self.manager.get_tasks()}
        self.assertEqual(titles, {"Finish SE proposal", "Read queue chapter",
                                  "Group meeting"})
        self.assertEqual(len(self.stored_records()), 3)


class TestIllegalInput(CliTestCase):
    """Every prompt reprompts instead of crashing (TC-I-28 ... TC-I-36)."""

    def test_unknown_menu_option_is_rejected_then_accepted(self) -> None:
        output, _ = self.session(["9", "", "abc", "2", "0"])
        self.assertEqual(output.count("Please enter one of: 0, 1, 2, 3, 4, 5, 6, 7."), 3)
        self.assertIn("No tasks to show.", output)

    def test_blank_title_and_course_are_rejected(self) -> None:
        output, _ = self.session(["1", "", "   ", "Real title", "", "SE", "", "3", "", "0"])
        self.assertEqual(output.count("This field cannot be empty."), 3)
        self.assertEqual(self.manager.get_task(self.first_id()).title, "Real title")

    def test_impossible_and_malformed_dates_are_rejected(self) -> None:
        output, _ = self.session(
            ["1", "Dec deadline", "SE", "2026-13-01", "2026-02-30", "20261120",
             "2026-1-5", "2026-12-10", "3", "", "0"])
        self.assertEqual(
            output.count("Enter a valid date in YYYY-MM-DD format, or leave it blank if allowed."),
            4)
        self.assertEqual(self.manager.get_task(self.first_id()).due_date, "2026-12-10")

    def test_blank_date_is_accepted_when_allowed(self) -> None:
        output, _ = self.session(self.add("No deadline", "SE", "") + ["0"])
        self.assertEqual(self.manager.get_task(self.first_id()).due_date, "")
        self.assertNotIn("Enter a valid date", output)

    def test_priority_rejects_out_of_range_and_text(self) -> None:
        output, _ = self.session(["1", "P task", "SE", "", "5", "abc", "0", "1", "", "0"])
        self.assertEqual(output.count("Priority must be 1, 2, 3, or 4."), 3)
        self.assertEqual(self.manager.get_task(self.first_id()).priority, 1)

    def test_priority_accepts_all_four_levels(self) -> None:
        for level in ("1", "2", "3", "4"):
            with self.subTest(priority=level):
                self.session(["1", f"P{level}", "SE", "", level, "", "0"])
        self.assertEqual(len({t.priority for t in self.manager.get_tasks()}), 4)

    def test_status_rejects_invalid_choice(self) -> None:
        self.session(self.add("S task", "SE"))
        output, _ = self.session(["4", self.first_id(), "5", "4", "", "2", "0"])
        self.assertEqual(output.count("Choose 1, 2, or 3."), 2)
        self.assertEqual(self.manager.get_task(self.first_id()).status, "In Progress")

    def test_unknown_id_is_reported_then_accepted_for_view(self) -> None:
        self.session(self.add("Real", "SE"))
        output, _ = self.session(["3", "nope", "   ", self.first_id(), "0"])
        self.assertEqual(output.count("Task not found: nope"), 1)
        self.assertIn("Title: Real", output)

    def test_unknown_id_is_reported_for_update_and_delete(self) -> None:
        output, _ = self.session(["4", "ghost", "5", "ghost", "0"])
        self.assertEqual(output.count("Task not found: ghost"), 2)

    def test_field_choice_outside_1_6_is_rejected(self) -> None:
        self.session(self.add("F task", "SE"))
        output, _ = self.session(["4", self.first_id(), "7", "1", "New", "0"])
        self.assertIn("Please enter one of: 1, 2, 3, 4, 5, 6.", output)
        self.assertEqual(self.manager.get_task(self.first_id()).title, "New")

    def test_filter_choice_outside_1_3_is_rejected(self) -> None:
        output, _ = self.session(["6", "0", "1", "SE", "0"])
        self.assertIn("Please enter one of: 1, 2, 3.", output)


class TestEofHandling(CliTestCase):
    """Input ending mid-flow closes cleanly and never half-saves a task."""

    def test_eof_during_add_does_not_create_a_partial_task(self) -> None:
        output, _ = self.session(["1", "Half typed"])
        self.assertIn("LearnTrack closed.", output)
        self.assertEqual(self.manager.statistics()["total"], 0)
        self.assertEqual(self.stored_records(), [])

    def test_eof_at_menu_prints_farewell(self) -> None:
        output, _ = self.session([])
        self.assertIn("LearnTrack closed.", output)


class TestBugPriorityUnicodeDigit(CliTestCase):
    """BUG-02: a superscript digit passes isdigit() but crashes int()."""

    def test_superscript_digit_should_be_rejected_gracefully(self) -> None:
        output, _ = self.session(["1", "Unicode priority", "SE", "", "²", "2", "", "0"])
        self.assertIn("Priority must be 1, 2, 3, or 4.", output)
        self.assertEqual(self.manager.get_task(self.first_id()).priority, 2)

    test_superscript_digit_should_be_rejected_gracefully = unittest.expectedFailure(
        test_superscript_digit_should_be_rejected_gracefully)


class TestBugCjkAlignment(CliTestCase):
    """BUG-03: column padding counts code points, not display width."""

    @staticmethod
    def display_cells(text: str) -> int:
        """Terminal width: CJK / full-width characters occupy two cells."""
        return sum(2 if east_asian_width(char) in "WF" else 1 for char in text)

    def test_cjk_course_keeps_the_title_column_aligned(self) -> None:
        self.session(self.add("CJK task", "软件工程", "2026-12-10", "1"))
        self.session(self.add("Ascii task", "Software Engineering", "2026-12-11", "1"))
        output, _ = self.session(["2", "0"])
        header = next(line for line in output.splitlines() if line.startswith("ID"))
        title_column = self.display_cells(header[:header.index("Title")])
        for line in output.splitlines():
            if "CJK task" in line or "Ascii task" in line:
                label = "CJK task" if "CJK task" in line else "Ascii task"
                column = self.display_cells(line[:line.index(label)])
                self.assertEqual(column, title_column,
                                 f"{label} starts at display column {column}, "
                                 f"header Title is at {title_column}")

    test_cjk_course_keeps_the_title_column_aligned = unittest.expectedFailure(
        test_cjk_course_keeps_the_title_column_aligned)


class TestBugChineseCommaSubtasks(CliTestCase):
    """BUG-04: full-width commas are not treated as subtask separators."""

    def test_fullwidth_comma_splits_subtasks(self) -> None:
        self.session(self.add("分隔符", "SE", "", "3", "读课本，做题，复习"))
        self.assertEqual(self.manager.get_task(self.first_id()).subtasks,
                         ["读课本", "做题", "复习"])

    test_fullwidth_comma_splits_subtasks = unittest.expectedFailure(
        test_fullwidth_comma_splits_subtasks)


class TestRealProcess(unittest.TestCase):
    """Out-of-process runs: the module really starts, saves and restarts."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.path = self.dir / "tasks.json"
        self.env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_app(self, answers: list[str]) -> subprocess.CompletedProcess:
        script = PROJECT_ROOT / "learntrack_cli.py"
        return subprocess.run(
            [sys.executable, str(script)],
            input="\n".join(answers) + "\n",
            cwd=str(self.dir), text=True, encoding="utf-8",
            capture_output=True, timeout=30, env=self.env,
        )

    def test_start_add_list_exit_then_restart_sees_the_task(self) -> None:
        first = self.run_app(["1", "End-to-end task", "Software Engineering",
                              "2026-12-10", "1", "Draft,Proofread", "2", "0"])
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("Goodbye.", first.stdout)
        self.assertIn("End-to-end task", first.stdout)
        self.assertTrue(self.path.exists())
        self.assertEqual(len(json.loads(self.path.read_text(encoding="utf-8"))), 1)

        second = self.run_app(["2", "7", "0"])
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("End-to-end task", second.stdout)
        self.assertIn("Total tasks: 1", second.stdout)

    def test_quit_immediately_creates_an_empty_store(self) -> None:
        result = self.run_app(["0"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Goodbye.", result.stdout)
        self.assertTrue(self.path.exists())  # boot creates an empty store
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), [])

    def test_delete_survives_a_restart(self) -> None:
        self.run_app(["1", "Temp", "SE", "", "3", "", "0"])
        task_id = json.loads(self.path.read_text(encoding="utf-8"))[0]["task_id"]
        self.run_app(["5", task_id, "y", "0"])
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), [])

    def test_unreadable_store_should_not_print_a_raw_traceback(self) -> None:
        (self.dir / "tasks.json").mkdir()  # a directory instead of a file
        result = self.run_app(["0"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("LearnTrack", result.stdout)

    test_unreadable_store_should_not_print_a_raw_traceback = unittest.expectedFailure(
        test_unreadable_store_should_not_print_a_raw_traceback)

    def test_utf8_bom_store_is_loaded_at_startup(self) -> None:
        payload = [{"task_id": "a" * 32, "title": "Bom task", "course": "SE",
                    "due_date": "", "priority": 2, "status": "To Do", "subtasks": []}]
        self.path.write_bytes(b"\xef\xbb\xbf" + json.dumps(payload).encode("utf-8"))
        result = self.run_app(["2", "0"])
        self.assertIn("Bom task", result.stdout)
        self.assertNotIn("No tasks to show.", result.stdout)

    test_utf8_bom_store_is_loaded_at_startup = unittest.expectedFailure(
        test_utf8_bom_store_is_loaded_at_startup)


if __name__ == "__main__":
    unittest.main(verbosity=2)
