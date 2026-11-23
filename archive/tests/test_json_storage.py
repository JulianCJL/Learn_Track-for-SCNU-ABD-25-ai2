"""Tests for json_storage_fixed — JSON persistence layer.

Every test uses its own temporary directory, so the project's tasks.json is
never touched. Scope: load/save contract, corruption recovery, and the
storage-backed manager that the real CLI boots from.

Runner: python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from json_storage_fixed import (  # noqa: E402
    PersistentTaskManager,
    create_manager,
    load_tasks,
    save_tasks,
)
from task import Task  # noqa: E402


class StorageTestCase(unittest.TestCase):
    """Base class handing each test a clean directory."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.path = self.dir / "tasks.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def records(self) -> list[dict]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def corrupt_backups(self) -> list[Path]:
        return [p for p in self.dir.iterdir() if "_corrupt_" in p.name]


class TestLoadTasks(StorageTestCase):
    """Load contract: missing file, empty file, envelope format (TC-S-01 ... TC-S-05)."""

    def test_missing_file_is_created_and_yields_an_empty_list(self) -> None:
        self.assertFalse(self.path.exists())
        self.assertEqual(load_tasks(self.path), [])
        self.assertTrue(self.path.exists())
        self.assertEqual(self.records(), [])

    def test_empty_file_yields_an_empty_list(self) -> None:
        self.path.write_text("", encoding="utf-8")
        self.assertEqual(load_tasks(self.path), [])

    def test_whitespace_only_file_yields_an_empty_list(self) -> None:
        self.path.write_text("   \n\n\t ", encoding="utf-8")
        self.assertEqual(load_tasks(self.path), [])

    def test_plain_list_is_loaded_in_file_order(self) -> None:
        payload = [
            {"task_id": "b", "title": "Second", "course": "SE", "priority": 2},
            {"task_id": "a", "title": "First", "course": "SE"},
        ]
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_tasks(self.path)
        self.assertEqual([t.task_id for t in loaded], ["b", "a"])
        self.assertEqual(loaded[0].priority, 2)

    def test_envelope_format_with_tasks_key_is_accepted(self) -> None:
        payload = {"version": 1, "tasks": [
            {"task_id": "a", "title": "First", "course": "SE"}]}
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_tasks(self.path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].task_id, "a")

    def test_utf8_bom_file_is_loaded(self) -> None:
        """BUG-01: a UTF-8 BOM (Notepad / PowerShell 5.1 output) breaks the load."""
        payload = [{"task_id": "a", "title": "First", "course": "SE"}]
        self.path.write_bytes(b"\xef\xbb\xbf" + json.dumps(payload).encode("utf-8"))
        self.assertEqual(len(load_tasks(self.path)), 1)

    test_utf8_bom_file_is_loaded = unittest.expectedFailure(test_utf8_bom_file_is_loaded)


class TestLoadValidation(StorageTestCase):
    """Invalid or duplicated records are skipped, valid ones survive (TC-S-06 ... TC-S-08)."""

    def test_invalid_record_is_skipped_and_valid_one_kept(self) -> None:
        payload = [
            {"task_id": "bad", "title": "Bad priority", "course": "SE", "priority": 9},
            {"task_id": "good", "title": "Valid", "course": "SE", "priority": 2},
        ]
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_tasks(self.path)
        self.assertEqual([t.task_id for t in loaded], ["good"])

    def test_duplicate_ids_keep_only_the_first_record(self) -> None:
        payload = [
            {"task_id": "dup", "title": "First", "course": "SE"},
            {"task_id": "dup", "title": "Second", "course": "SE"},
        ]
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_tasks(self.path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].title, "First")

    def test_non_object_entries_are_skipped(self) -> None:
        payload = ["just a string", 5, None,
                   {"task_id": "ok", "title": "Valid", "course": "SE"}]
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_tasks(self.path)
        self.assertEqual([t.task_id for t in loaded], ["ok"])

    def test_record_missing_a_mandatory_field_is_skipped(self) -> None:
        payload = [{"task_id": "a", "title": "No course"}]
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(load_tasks(self.path), [])


class TestSaveTasks(StorageTestCase):
    """Save contract: atomic write, round trip, type guard (TC-S-09 ... TC-S-12)."""

    def test_save_returns_the_number_of_records_and_writes_valid_json(self) -> None:
        tasks = [Task("a", "t1", "SE"), Task("b", "t2", "AI")]
        self.assertEqual(save_tasks(tasks, self.path), 2)
        self.assertEqual(len(self.records()), 2)

    def test_saved_file_keeps_every_protocol_field(self) -> None:
        original = Task("a", "复习第四章", "数据结构", "2026-11-20", 1,
                        "In Progress", ["Ch1", "Ch2"])
        save_tasks([original], self.path)
        self.assertEqual(self.records()[0], original.to_dict())

    def test_round_trip_through_load_is_lossless(self) -> None:
        original = Task("a", "t", "SE", "2026-11-20", 1, "Completed", ["x"])
        save_tasks([original], self.path)
        self.assertEqual(load_tasks(self.path)[0].to_dict(), original.to_dict())

    def test_saving_an_empty_list_clears_the_file(self) -> None:
        save_tasks([Task("a", "t", "SE")], self.path)
        save_tasks([], self.path)
        self.assertEqual(self.records(), [])

    def test_non_task_objects_are_rejected(self) -> None:
        for bad in (["not a task"], [None], [{"task_id": "a"}]):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    save_tasks(bad, self.path)  # type: ignore[arg-type]

    def test_in_place_corrupted_subtasks_are_rejected_before_writing(self) -> None:
        task = Task("a", "t", "SE", subtasks=["Draft"])
        task.subtasks.append(123)
        with self.assertRaises(ValueError):
            save_tasks([task], self.path)

    def test_write_leaves_no_temporary_files_behind(self) -> None:
        save_tasks([Task("a", "t", "SE")], self.path)
        self.assertEqual([p.name for p in self.dir.iterdir()], ["tasks.json"])

    def test_save_creates_the_parent_directory_when_missing(self) -> None:
        nested = self.dir / "data" / "tasks.json"
        self.assertEqual(save_tasks([Task("a", "t", "SE")], nested), 1)
        self.assertTrue(nested.exists())

    def test_overwriting_keeps_the_file_parseable(self) -> None:
        save_tasks([Task("a", "t", "SE")], self.path)
        save_tasks([Task("b", "t2", "AI")], self.path)
        self.assertEqual([t.task_id for t in load_tasks(self.path)], ["b"])


class TestCorruptionRecovery(StorageTestCase):
    """Damaged files are backed up, then rebuilt empty (TC-S-13 ... TC-S-16)."""

    def test_malformed_json_is_backed_up_and_replaced_by_an_empty_list(self) -> None:
        self.path.write_text("{ not valid json ", encoding="utf-8")
        self.assertEqual(load_tasks(self.path), [])
        self.assertEqual(len(self.corrupt_backups()), 1)
        self.assertEqual(self.records(), [])
        backup = self.corrupt_backups()[0]
        self.assertEqual(backup.read_text(encoding="utf-8"), "{ not valid json ")

    def test_non_utf8_bytes_are_treated_as_corruption(self) -> None:
        self.path.write_bytes(b"\xff\xfe\x00bad")
        self.assertEqual(load_tasks(self.path), [])
        self.assertTrue(self.corrupt_backups())

    def test_top_level_object_that_is_not_a_task_list_is_rebuilt(self) -> None:
        self.path.write_text(json.dumps({"version": 1, "tasks": "oops"}),
                             encoding="utf-8")
        self.assertEqual(load_tasks(self.path), [])
        self.assertTrue(self.corrupt_backups())

    def test_rebuilt_file_can_be_used_again(self) -> None:
        self.path.write_text("{ broken", encoding="utf-8")
        self.assertEqual(load_tasks(self.path), [])
        manager = create_manager(self.path)
        manager.add_task("After recovery", "SE")
        self.assertEqual(len(load_tasks(self.path)), 1)


class TestIOException(StorageTestCase):
    """Read failures are reported, never silently replaced by an empty list."""

    def test_unreadable_path_raises_oserror_instead_of_an_empty_list(self) -> None:
        blocked = self.dir / "tasks.json"
        blocked.mkdir()  # a directory cannot be read as a file
        with self.assertRaises(OSError):
            load_tasks(blocked)

    def test_missing_path_object_does_not_crash(self) -> None:
        self.assertEqual(load_tasks(self.dir / "never" / "tasks.json"), [])


class TestPersistentTaskManager(StorageTestCase):
    """The manager used by the real CLI writes through on every mutation."""

    def setUp(self) -> None:
        super().setUp()
        self.manager = create_manager(self.path)

    def test_add_is_persisted(self) -> None:
        created = self.manager.add_task("Finish proposal", "SE", "2026-11-20", 1,
                                        ["Draft"])
        self.assertEqual(len(load_tasks(self.path)), 1)
        self.assertEqual(load_tasks(self.path)[0].to_dict(), created.to_dict())

    def test_update_is_persisted(self) -> None:
        created = self.manager.add_task("t", "SE")
        self.manager.update_task(created.task_id, status="Completed", priority=2)
        reopened = create_manager(self.path)
        self.assertEqual(reopened.get_task(created.task_id).status, "Completed")
        self.assertEqual(reopened.get_task(created.task_id).priority, 2)

    def test_delete_is_persisted(self) -> None:
        keep = self.manager.add_task("keep", "SE")
        drop = self.manager.add_task("drop", "SE")
        self.manager.delete_task(drop.task_id)
        reopened = create_manager(self.path)
        self.assertEqual([t.task_id for t in reopened.get_tasks()],
                         [keep.task_id])

    def test_session_survives_a_restart(self) -> None:
        created = self.manager.add_task("Persisted", "SE", "2026-11-20", 2, ["a"])
        reopened = create_manager(self.path)
        self.assertEqual(reopened.statistics()["total"], 1)
        self.assertEqual(reopened.get_task(created.task_id).subtasks, ["a"])

    def test_failed_save_is_reported_and_keeps_the_change_in_memory(self) -> None:
        blocked = self.dir / "blocked.json"
        blocked.mkdir()
        manager = PersistentTaskManager(None, blocked)
        created = manager.add_task("Stays in memory", "SE")
        self.assertTrue(manager.last_save_failed)
        self.assertEqual(manager.get_task(created.task_id).title, "Stays in memory")
        self.assertEqual(manager.statistics()["total"], 1)

    def test_successful_save_clears_the_failure_flag(self) -> None:
        blocked = self.dir / "blocked.json"
        blocked.mkdir()
        manager = PersistentTaskManager(None, blocked)
        manager.add_task("t", "SE")
        self.assertTrue(manager.last_save_failed)
        manager.storage_path = self.path      # destination becomes writable again
        manager.add_task("t2", "SE")
        self.assertFalse(manager.last_save_failed)
        self.assertEqual(len(load_tasks(self.path)), 2)

    def test_inherited_read_methods_work_on_the_persistent_manager(self) -> None:
        manager = create_manager(self.path)
        self.assertEqual(manager.get_tasks(), [])
        self.assertEqual(manager.filter_tasks(course="SE"), [])
        self.assertEqual(manager.statistics()["total"], 0)


class TestKnownLimitationConcurrentInstances(StorageTestCase):
    """BUG-06: no file locking, so two running copies overwrite each other."""

    def test_two_managers_over_one_file_keep_both_tasks(self) -> None:
        first = create_manager(self.path)
        second = create_manager(self.path)
        first.add_task("Added by window A", "SE")
        second.add_task("Added by window B", "AI")
        self.assertEqual({t.title for t in load_tasks(self.path)},
                         {"Added by window A", "Added by window B"})

    test_two_managers_over_one_file_keep_both_tasks = unittest.expectedFailure(
        test_two_managers_over_one_file_keep_both_tasks)


if __name__ == "__main__":
    unittest.main(verbosity=2)
