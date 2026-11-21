"""Regression check for the six bugs fixed in this folder (BUG-01 ... BUG-06).

Self-contained: every case runs in a temporary directory and the CLI is started
in that directory, so the project's own tasks.json is never touched.

    python verify_bug_fixes.py      # from this folder, or with an absolute path

Exit code 0 = all checks pass, 1 = at least one check failed.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unicodedata import east_asian_width
from unittest import mock

PROJECT = Path(__file__).resolve().parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from json_storage_fixed import create_manager, load_tasks  # noqa: E402
from learntrack_cli import run_cli, split_subtasks  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))


class Feed:
    """Scripted keyboard input for one CLI session."""

    def __init__(self, answers: list[object]) -> None:
        self.queue = list(answers)
        self.prompts: list[str] = []

    def __call__(self, prompt: str = "") -> str:
        self.prompts.append(prompt)
        if not self.queue:
            raise EOFError
        item = self.queue.pop(0)
        return item(prompt) if callable(item) else str(item)  # type: ignore[return-value]


def session(manager, answers: list[object]) -> tuple[str, Feed]:
    feed = Feed(answers)
    out = io.StringIO()
    with mock.patch("builtins.input", new=feed), contextlib.redirect_stdout(out):
        run_cli(manager)
    return out.getvalue(), feed


def cells(text: str) -> int:
    return sum(2 if east_asian_width(char) in "WF" else 1 for char in text)


def check_bug_01(root: Path) -> None:
    """A UTF-8 BOM must not be mistaken for corruption."""
    path = root / "bom" / "tasks.json"
    path.parent.mkdir(parents=True)
    payload = [{"task_id": "a" * 32, "title": "Existing task", "course": "SE",
                "due_date": "2026-12-10", "priority": 2, "status": "To Do",
                "subtasks": ["Draft"]}]
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(payload, ensure_ascii=False).encode())
    loaded = load_tasks(path)
    no_backup = not any("_corrupt_" in item.name for item in path.parent.iterdir())
    record("BUG-01 UTF-8 BOM 不再被判为损坏", len(loaded) == 1 and no_backup,
           f"loaded={len(loaded)}, corrupt_backup={not no_backup}")


def check_bug_02(root: Path) -> None:
    """A superscript digit must be rejected, not crash int()."""
    manager = create_manager(root / "prio" / "tasks.json")
    output, _ = session(manager, ["1", "Prio task", "SE", "", "\u00b2", "2", "", "0"])
    rejected = "Priority must be 1, 2, 3, or 4." in output
    no_crash = "Unable to complete that action" not in output
    saved = len(manager.get_tasks()) == 1 and manager.get_tasks()[0].priority == 2
    record("BUG-02 上标数字被正常拒绝", rejected and no_crash and saved,
           f"rejected={rejected}, no_crash={no_crash}, saved={saved}")


def check_bug_03(root: Path) -> None:
    """CJK course names must keep the Title column aligned."""
    manager = create_manager(root / "cjk" / "tasks.json")
    session(manager, ["1", "CJK course task", "软件工程", "2026-12-10", "1", "", "0"])
    session(manager, ["1", "Long CJK course", "计算机科学与技术学院软件工程导论课程", "", "2", "", "0"])
    session(manager, ["1", "Ascii course task", "Software Engineering", "2026-12-11", "2", "", "0"])
    output, _ = session(manager, ["2", "0"])
    header = next(line for line in output.splitlines() if line.startswith("ID"))
    target = cells(header[:header.index("Title")])
    aligned = True
    for title in ("CJK course task", "Long CJK course", "Ascii course task"):
        row = next(line for line in output.splitlines() if title in line)
        aligned &= cells(row[:row.index(title)]) == target
    record("BUG-03 中文课程名不再错位", aligned, f"title_column={target}")


def check_bug_04(root: Path) -> None:
    """Full-width commas must split subtasks, in add and in update."""
    pure = (split_subtasks("读课本，做题，复习") == ["读课本", "做题", "复习"]
            and split_subtasks("A,B") == ["A", "B"]
            and split_subtasks("A，B,C") == ["A", "B", "C"]
            and split_subtasks("") == [])
    manager = create_manager(root / "comma" / "tasks.json")
    session(manager, ["1", "分隔符", "SE", "", "3", "读课本，做题，复习", "0"])
    added = manager.get_tasks()[0].subtasks == ["读课本", "做题", "复习"]
    session(manager, ["4", manager.get_tasks()[0].task_id, "6", "第一章，第二章", "0"])
    updated = manager.get_tasks()[0].subtasks == ["第一章", "第二章"]
    record("BUG-04 全角逗号分割子任务", pure and added and updated,
           f"pure={pure}, add={added}, update={updated}")


def check_bug_05(root: Path) -> None:
    """An unreadable store must fail with a message, not a traceback."""
    work = root / "locked"
    work.mkdir(parents=True)
    (work / "tasks.json").mkdir()
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, str(PROJECT / "learntrack_cli.py")],
        input="0\n", cwd=str(work), text=True, encoding="utf-8",
        capture_output=True, timeout=30, env=env,
    )
    friendly = "LearnTrack cannot start" in result.stdout
    no_trace = "Traceback" not in result.stderr
    record("BUG-05 读不出文件时给出提示而非 traceback",
           result.returncode == 1 and friendly and no_trace,
           f"returncode={result.returncode}, message={friendly}, no_trace={no_trace}")


def check_bug_06(root: Path) -> None:
    """A second instance must keep the other version instead of losing it."""
    shared = root / "shared" / "tasks.json"
    first = create_manager(shared)
    second = create_manager(shared)
    first.add_task("Added by window A", "SE")
    second.add_task("Added by window B", "AI")
    conflicts = [item for item in shared.parent.iterdir() if "_conflict_" in item.name]
    kept = bool(conflicts) and "Added by window A" in conflicts[0].read_text(encoding="utf-8")
    detected = second.external_change and not first.external_change
    record("BUG-06 并发写不静默丢数据", detected and kept,
           f"detected={detected}, snapshot_kept={kept}")


def check_regression(root: Path) -> None:
    """The whole menu still works end to end and still persists."""
    manager = create_manager(root / "flow" / "tasks.json")
    answers: list[object] = []
    answers += ["1", "Finish SE proposal", "Software Engineering", "2026-12-10", "1", "Draft,Proofread"]
    answers += ["1", "Revise AI midterm", "Artificial Intelligence", "", "2", ""]
    answers += ["1", "Read queue chapter", "Data Structures", "2026-11-15", "3", "Ch2,Ch3"]
    answers += ["2"]
    answers += ["3", lambda p: manager.get_tasks()[0].task_id]
    answers += ["4", lambda p: manager.get_tasks()[0].task_id, "5", "2"]
    answers += ["6", "1", "Software Engineering", "6", "2", "3", "6", "3"]
    answers += ["7"]
    answers += ["5", lambda p: manager.get_tasks()[-1].task_id, "y"]
    answers += ["0"]
    output, feed = session(manager, answers)
    markers = ("1. Add task", "2. List tasks", "3. View task details", "4. Update task",
               "5. Delete task", "6. Filter tasks", "7. View statistics",
               "Added task", "Updating ", "Updated task", "Task deleted.",
               "Task statistics", "Goodbye.")
    ok = all(marker in output for marker in markers) and feed.queue == []
    reopened = create_manager(root / "flow" / "tasks.json")
    persisted = len(reopened.get_tasks()) == 2
    record("REGRESSION 全菜单流程与落盘", ok and persisted, f"menus={ok}, persisted={persisted}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="learntrack_verify_") as tmp:
        root = Path(tmp)
        check_bug_01(root)
        check_bug_02(root)
        check_bug_03(root)
        check_bug_04(root)
        check_bug_05(root)
        check_bug_06(root)
        check_regression(root)

    print("LearnTrack bug-fix verification")
    print("=" * 52)
    for name, ok, detail in RESULTS:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    failed = [name for name, ok, _ in RESULTS if not ok]
    print("-" * 52)
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
