"""JsonStorage — tasks.json 读写层（LearnTrack PoC）。

读取：tasks.json → Task 列表 → TaskManager
写入：add / update / delete 之后把整张表原子写回。

相对早期版本的改动：
1. 读不出来时抛 OSError，不再假装"空表"（否则下一次保存会把用户数据整个覆盖）。
2. 写入改成原子替换（临时文件 → fsync → os.replace），中途崩不会毁掉原文件。
3. 恢复文件时去重 task_id，否则 TaskManager.__init__ 会直接 ValueError 崩掉启动。
4. 损坏文件先另存 *_corrupt_*.json 再重建。
5. 路径可注入，便于测试；不再写死 CWD。
6. 用继承代替手工转发包装类，新增的 TaskManager 方法自动生效。
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


# ------------------------------------------------------------------ 内部读写

def _backup_beside(path: Path, tag: str) -> Path | None:
    """留一份副本：tasks_<tag>_YYYYMMDD_HHMMSS.json"""
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = path.with_name(f"{path.stem}_{tag}_{stamp}{path.suffix}")
    try:
        dest.write_bytes(path.read_bytes())
    except OSError:
        return None
    return dest


def _write_json(path: Path, records: list[dict]) -> None:
    """原子写：临时文件 → flush → fsync → os.replace。失败抛 OSError。"""
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
    backup = _backup_beside(path, "corrupt")
    print(f"Warning: {reason}；原文件已另存为 {backup}，重建空表。")
    _write_json(path, [])


# ----------------------------------------------------------------------- 读

def load_tasks(path: str | Path = DATA_FILE) -> list[Task]:
    """从文件恢复 Task 列表。

    文件不存在 → 建空文件并返回 []。
    读不出来（权限不足、被占用）→ 抛 OSError。绝不降级成空表：
    空表一旦被保存，原数据就没了。
    """
    path = Path(path)
    if not path.exists():
        _write_json(path, [])
        return []

    raw = path.read_bytes()          # OSError 交给调用方
    try:
        text = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        _rebuild_empty(path, f"{path} 不是 UTF-8 文本")
        return []
    if not text:
        return []

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        _rebuild_empty(path, f"{path} 解析失败")
        return []

    if isinstance(data, dict):       # 兼容 {"version":…, "tasks":[…]} 信封格式
        data = data.get("tasks", [])
    if not isinstance(data, list):
        _rebuild_empty(path, f"{path} 顶层不是任务列表")
        return []

    tasks: list[Task] = []
    seen: set[str] = set()
    for item in data:
        try:
            task = Task.from_dict(item)
        except ValueError as err:
            print(f"Skipping invalid task data: {err}")
            continue
        if task.task_id in seen:
            print(f"Skipping duplicate task ID: {task.task_id}")
            continue
        seen.add(task.task_id)
        tasks.append(task)
    return tasks


# ----------------------------------------------------------------------- 写

def save_tasks(tasks: Iterable[Task], path: str | Path = DATA_FILE) -> int:
    """把整张表写回文件，返回写入条数。失败抛 OSError，不吞、不撒谎。"""
    records = []
    for task in tasks:
        if not isinstance(task, Task):
            raise ValueError("storage only accepts Task objects")
        records.append(task.to_dict())     # 被就地改过的 subtasks 在这里被 validate 拦住
    _write_json(Path(path), records)
    return len(records)


class PersistentTaskManager(TaskManager):
    """继承 TaskManager，只重写三个会改数据的方法，其余全部原样继承。

    保存失败会打印 Error 并把 last_save_failed 置 True，内存里的改动保留，
    下次成功保存时会一起落盘。
    """

    def __init__(self, tasks: Iterable[Task] | None = None,
                 path: str | Path = DATA_FILE) -> None:
        super().__init__(tasks)
        self.storage_path = Path(path)
        self.last_save_failed = False

    def _persist(self) -> None:
        try:
            save_tasks(self.get_tasks(), self.storage_path)
            self.last_save_failed = False
        except (OSError, ValueError) as exc:
            self.last_save_failed = True
            print(f"Error: 保存失败，本次改动仅在内存中（{exc}）")

    # Overrides keep the exact TaskManagerPort signatures so callers (and the
    # CLI's documented interface) bind arguments identically on both classes.
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
    """启动入口：从 path 读出任务并返回会自保存的 manager。"""
    return PersistentTaskManager(load_tasks(path), path)


# ------------------------------------------------------------------ 自检

def _self_test() -> None:
    import tempfile as tf
    import pathlib

    workdir = pathlib.Path(tf.mkdtemp())
    path = workdir / "tasks.json"
    print("JsonStorage self-test")
    print("=" * 40)

    print("1. 文件不存在时建空表:", load_tasks(path) == [] and path.exists())

    manager = create_manager(path)
    first = manager.add_task("Finish SE proposal", "Software Engineering",
                             "2026-11-20", 1, ["Draft", "Proofread"])
    manager.add_task("Revise for AI midterm", "Artificial Intelligence", "2026-11-25", 2)
    manager.add_task("Read queue chapter", "Data Structures", "", 3)
    print("2. 三条任务已落盘:", len(load_tasks(path)))

    reopened = create_manager(path)
    print("3. 重新打开数量一致:", len(reopened.get_tasks()) == 3)
    print("4. 字段完全还原:",
          reopened.get_task(first.task_id).to_dict() == first.to_dict())

    reopened.update_task(first.task_id, status="Completed")
    print("5. update 已持久化:", create_manager(path).get_task(first.task_id).status)
    reopened.delete_task(first.task_id)
    print("6. delete 已持久化:", len(create_manager(path).get_tasks()) == 2)
    print("7. 继承来的方法可用:",
          isinstance(reopened, TaskManager) and reopened.statistics()["total"] == 2)

    path.write_text("{ not valid json ", encoding="utf-8")
    print("8. 损坏文件返回空表:", load_tasks(path) == [])
    print("9. 损坏副本已保留:", any("_corrupt_" in p.name for p in workdir.iterdir()))
    print("10. 重建后可继续用:", path.exists() and load_tasks(path) == [])

    path.write_text(json.dumps([
        {"task_id": "abc123", "title": "Bad priority", "course": "SE",
         "priority": 9, "status": "To Do", "due_date": "", "subtasks": []},
        {"task_id": "abc123", "title": "Duplicate", "course": "SE",
         "priority": 2, "status": "To Do", "due_date": "", "subtasks": []},
        {"task_id": "def456", "title": "Valid task", "course": "SE",
         "priority": 2, "status": "To Do", "due_date": "", "subtasks": []},
    ]), encoding="utf-8")
    print("11. 非法记录跳过、重复 ID 去重:", len(load_tasks(path)) == 2)

    path.write_bytes(b"\xff\xfe\x00bad")
    print("12. 非 UTF-8 文件也走损坏分支:", load_tasks(path) == [])

    path.unlink()
    workdir.joinpath("x").touch()
    for p in workdir.iterdir():
        p.unlink()
    workdir.rmdir()


if __name__ == "__main__":
    _self_test()
