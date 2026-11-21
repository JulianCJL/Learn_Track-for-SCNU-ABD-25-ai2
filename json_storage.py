"""JSON persistence layer for LearnTrack.

``load_tasks`` restores Task objects from a JSON file; ``save_tasks`` writes
the whole task list back. The storage-backed manager persists every add,
update, and delete through an atomic file replacement.

Damaged, unreadable, or partially invalid data is copied beside the original
file before it is dropped or rebuilt, so a recoverable backup exists when
the file permissions allow it.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from task import Task
from task_manager import TaskManager

DATA_FILE = Path("tasks.json")


# --------------------------------------------------------------------- helpers

def _backup_beside(path: Path, tag: str) -> Path | None:
    """Copy the file to ``<stem>_<tag>_<timestamp><suffix>`` next to it."""
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = path.with_name(f"{path.stem}_{tag}_{stamp}{path.suffix}")
    try:
        dest.write_bytes(path.read_bytes())
    except OSError:
        return None
    return dest


def _file_signature(path: Path) -> tuple[int, int] | None:
    """Return the file's ``(mtime_ns, size)``; ``None`` when it cannot be read."""
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def _write_json(path: Path, records: list[dict]) -> None:
    """Replace the file atomically: temp file, flush, fsync, rename."""
    parent = path.parent if str(path.parent) else Path(".")
    if not parent.is_dir():
        parent.mkdir(parents=True, exist_ok=True)
    handle = None
    temp_name = None
    try:
        handle = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".tmp",
            dir=str(parent), delete=False,
        )
        temp_name = handle.name
        json.dump(records, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        handle = None
        os.replace(temp_name, path)
        temp_name = None
    finally:
        if handle is not None:
            handle.close()
        if temp_name and os.path.exists(temp_name):
            os.remove(temp_name)


def _rebuild_empty(path: Path, reason: str) -> None:
    """Back up the damaged file, then replace it with an empty list."""
    backup = _backup_beside(path, "corrupt")
    if backup is None:
        # Without a backup copy, rebuilding would destroy the only data copy.
        raise OSError(f"cannot back up {path} before rebuilding it")
    print(f"Warning: {reason}; the original file was saved as {backup} "
          "and an empty list was rebuilt.")
    _write_json(path, [])


# --------------------------------------------------------------------- loading

def load_tasks(path: str | Path = DATA_FILE) -> list[Task]:
    """Restore the Task list stored in ``path``.

    A missing file is created as an empty list. Files with a UTF-8 BOM are
    decoded normally. Read or parse failures are reported through the backup
    and rebuild path instead of silently pretending the store is empty.
    """
    path = Path(path)
    if not path.exists():
        _write_json(path, [])
        return []

    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig").strip()
    except UnicodeDecodeError:
        _rebuild_empty(path, f"{path} is not UTF-8 text")
        return []
    if not text:
        return []

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        _rebuild_empty(path, f"{path} could not be parsed as JSON")
        return []

    # Accept either a plain list or an envelope such as {"version": 1, "tasks": [...]}.
    if isinstance(data, dict):
        data = data.get("tasks", [])
    if not isinstance(data, list):
        _rebuild_empty(path, f"{path} does not contain a task list")
        return []

    tasks: list[Task] = []
    seen: set[str] = set()
    skipped = 0
    for item in data:
        try:
            task = Task.from_dict(item)
        except ValueError as err:
            print(f"Skipping invalid task data: {err}")
            skipped += 1
            continue
        if task.task_id in seen:
            print(f"Skipping duplicate task ID: {task.task_id}")
            skipped += 1
            continue
        seen.add(task.task_id)
        tasks.append(task)

    # Keep a copy of the original file before the skipped records are dropped
    # by the next save, so they can be recovered manually if needed.
    if skipped:
        backup = _backup_beside(path, "skipped")
        if backup is None:
            print(f"Warning: {skipped} record(s) could not be loaded and were "
                  "not kept; no backup copy could be written.")
        else:
            print(f"Warning: {skipped} record(s) could not be loaded; the "
                  f"original file was backed up to {backup}. They will not be "
                  "saved again.")
    return tasks


# --------------------------------------------------------------------- saving

def save_tasks(tasks: Iterable[Task], path: str | Path = DATA_FILE) -> int:
    """Write the whole list back to ``path`` and return the record count."""
    records = []
    for task in tasks:
        if not isinstance(task, Task):
            raise ValueError("storage only accepts Task objects")
        # In-place subtask edits are validated here before anything is written.
        records.append(task.to_dict())
    _write_json(Path(path), records)
    return len(records)


class PersistentTaskManager(TaskManager):
    """TaskManager that writes every mutation through to the JSON file.

    Read methods are inherited unchanged. When a save fails, the change is
    kept in memory and ``last_save_failed`` is set so the caller can report it.
    """

    def __init__(self, tasks: Iterable[Task] | None = None,
                 path: str | Path = DATA_FILE) -> None:
        super().__init__(tasks)
        self.storage_path = Path(path)
        self.last_save_failed = False
        self.external_change = False
        self._signature = _file_signature(self.storage_path)

    def _persist(self) -> None:
        try:
            self._snapshot_external_change()
            save_tasks(self.get_tasks(), self.storage_path)
            self._signature = _file_signature(self.storage_path)
            self.last_save_failed = False
        except (OSError, ValueError) as exc:
            self.last_save_failed = True
            print(f"Error: could not save changes; they are kept in memory only ({exc})")

    def _snapshot_external_change(self) -> None:
        """Preserve the on-disk version when another instance changed the file."""
        current = _file_signature(self.storage_path)
        if current is None or self._signature is None or current == self._signature:
            return
        backup = _backup_beside(self.storage_path, "conflict")
        self.external_change = True
        if backup is None:
            print("Warning: the task file was modified by another instance, "
                  "but no backup copy could be kept; this save will overwrite "
                  "those changes.")
        else:
            print(f"Warning: the task file was modified by another instance; "
                  f"the on-disk version was saved to {backup} and this save "
                  "will overwrite it.")

    # Overrides keep the same signatures as the base manager so callers bind
    # arguments identically on both classes.
    def add_task(
        self, title: str, course: str, due_date: str = "",
        priority: int = 3, subtasks: list[str] | None = None,
    ) -> Task:
        task = super().add_task(title, course, due_date, priority, subtasks)
        self._persist()
        return task

    def update_task(self, task_id: str, **updates: Any) -> Task:
        task = super().update_task(task_id, **updates)
        self._persist()
        return task

    def delete_task(self, task_id: str) -> Task:
        task = super().delete_task(task_id)
        self._persist()
        return task


def create_manager(path: str | Path = DATA_FILE) -> PersistentTaskManager:
    """Build a self-saving manager by loading tasks from ``path``."""
    return PersistentTaskManager(load_tasks(path), path)


# --------------------------------------------------------------------- self-test

def _self_test() -> None:
    import tempfile as tf
    import pathlib

    workdir = pathlib.Path(tf.mkdtemp())
    path = workdir / "tasks.json"
    print("JsonStorage self-test")
    print("=" * 40)

    print("1. Missing file creates an empty store:", load_tasks(path) == [] and path.exists())

    manager = create_manager(path)
    first = manager.add_task("Finish SE proposal", "Software Engineering",
                             "2026-11-20", 1, ["Draft", "Proofread"])
    manager.add_task("Revise AI midterm", "Artificial Intelligence", "2026-11-25", 2)
    manager.add_task("Read queue chapter", "Data Structures", "", 3)
    print("2. Three tasks persisted:", len(load_tasks(path)))

    reopened = create_manager(path)
    print("3. Count matches after reopening:", len(reopened.get_tasks()) == 3)
    print("4. Fields restored exactly:",
          reopened.get_task(first.task_id).to_dict() == first.to_dict())

    reopened.update_task(first.task_id, status="Completed")
    print("5. Update persisted:", create_manager(path).get_task(first.task_id).status)
    reopened.delete_task(first.task_id)
    print("6. Delete persisted:", len(create_manager(path).get_tasks()) == 2)
    print("7. Inherited methods work:",
          isinstance(reopened, TaskManager) and reopened.statistics()["total"] == 2)

    path.write_text("{ not valid json ", encoding="utf-8")
    print("8. Corrupt file returns an empty list:", load_tasks(path) == [])
    print("9. Corrupt backup kept:", any("_corrupt_" in p.name for p in workdir.iterdir()))
    print("10. Store reusable after rebuild:", path.exists() and load_tasks(path) == [])

    path.write_text(json.dumps([
        {"task_id": "abc123", "title": "Bad priority", "course": "SE",
         "priority": 9, "status": "To Do", "due_date": "", "subtasks": []},
        {"task_id": "abc123", "title": "Duplicate", "course": "SE",
         "priority": 2, "status": "To Do", "due_date": "", "subtasks": []},
        {"task_id": "def456", "title": "Valid task", "course": "SE",
         "priority": 2, "status": "To Do", "due_date": "", "subtasks": []},
    ]), encoding="utf-8")
    print("11. Invalid records skipped and duplicate IDs removed:",
          len(load_tasks(path)) == 2)

    path.write_bytes(b"\xff\xfe\x00bad")
    print("12. Non-UTF-8 bytes go through the corrupt branch:", load_tasks(path) == [])

    path.unlink()
    bom = workdir / "bom.json"
    bom.write_bytes(b"\xef\xbb\xbf" + json.dumps(
        [{"task_id": "bom1", "title": "BOM task", "course": "SE"}]).encode("utf-8"))
    print("13. UTF-8 BOM file loads normally:", len(load_tasks(bom)) == 1)

    shared = workdir / "shared.json"
    first = create_manager(shared)
    second = create_manager(shared)
    first.add_task("From window A", "SE")
    second.add_task("From window B", "AI")
    conflicts = [p.name for p in workdir.iterdir() if "_conflict_" in p.name]
    print("14. External change detected and backed up:",
          second.external_change and len(conflicts) == 1)

    for p in workdir.iterdir():
        p.unlink()
    workdir.rmdir()


if __name__ == "__main__":
    _self_test()
